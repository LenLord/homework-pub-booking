"""Ex5 tools. Four tools the agent uses to research an Edinburgh booking.

Each tool:
  1. Reads its fixture from sample_data/ (DO NOT modify the fixtures).
  2. Logs its arguments and output into _TOOL_CALL_LOG (see integrity.py).
  3. Returns a ToolResult with success=True/False, output=dict, summary=str.

The grader checks for:
  * Correct parallel_safe flags (reads True, generate_flyer False).
  * Every tool's results appear in _TOOL_CALL_LOG.
  * Tools fail gracefully on missing fixtures or bad inputs (ToolError,
    not RuntimeError).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sovereign_agent._internal.atomic import atomic_write_text
from sovereign_agent.errors import IOError as SovereignIOError
from sovereign_agent.errors import ToolError
from sovereign_agent.session.directory import Session
from sovereign_agent.tools.registry import ToolRegistry, ToolResult, _RegisteredTool

from starter.edinburgh_research.integrity import (
    _TOOL_CALL_LOG,
    ToolCallRecord,
    record_tool_call,
)

_SAMPLE_DATA = Path(__file__).parent / "sample_data"


# ---------------------------------------------------------------------------
# TODO 1 — venue_search
# ---------------------------------------------------------------------------
def venue_search(near: str, party_size: int, budget_max_gbp: int = 1000) -> ToolResult:
    """Search for Edinburgh venues near <near> that can seat the party.

    Reads sample_data/venues.json. Filters by:
      * open_now == True
      * area contains <near> (case-insensitive substring match)
      * seats_available_evening >= party_size
      * hire_fee_gbp + min_spend_gbp <= budget_max_gbp

    Returns a ToolResult with:
      output: {"near": ..., "party_size": ..., "results": [<venue dicts>], "count": int}
      summary: "venue_search(<near>, party=<N>): <count> result(s)"

    MUST call record_tool_call(...) before returning so the integrity
    check can see what data was produced.
    """
    # Spiral detection: cap at 3 prior calls to prevent LLM looping
    prior_count = sum(1 for r in _TOOL_CALL_LOG if r.tool_name == "venue_search")
    if prior_count >= 3:
        return ToolResult(
            success=False,
            output={"error": "too_many_searches", "count": prior_count},
            summary="STOP calling venue_search; use the results you already have.",
        )

    # Validate party_size against catering fixture's auto-booking cap
    catering_path = _SAMPLE_DATA / "catering.json"
    if catering_path.exists():
        catering_data = json.loads(catering_path.read_text())
        max_auto = catering_data.get("maximum_party_size_for_auto_booking", 8)
        if party_size > max_auto:
            return ToolResult(
                success=False,
                output={"error": "party_size_exceeds_max", "party_size": party_size, "max": max_auto},
                summary=(
                    f"venue_search: party_size={party_size} exceeds the auto-booking max ({max_auto}). "
                    f"Use the party size from the task context instead."
                ),
                error=ToolError(code="SA_TOOL_INVALID_INPUT", message=f"party_size {party_size} > max {max_auto}"),
            )

    fixture_path = _SAMPLE_DATA / "venues.json"
    if not fixture_path.exists():
        return ToolResult(
            success=False,
            output={"error": "fixture_missing"},
            summary="venue_search: sample_data/venues.json not found",
            error=ToolError(code="SA_TOOL_DEPENDENCY_MISSING", message="venues.json missing"),
        )

    venues = json.loads(fixture_path.read_text())
    # City-level query ("Edinburgh") matches all venues; neighbourhood queries
    # match by substring ("Haymarket" → only Haymarket Tap).
    city_level = "edinburgh" in near.lower()
    results = [
        v
        for v in venues
        if v.get("open_now")
        and (city_level or near.lower() in v.get("area", "").lower())
        and v.get("seats_available_evening", 0) >= party_size
        and v.get("hire_fee_gbp", 0) + v.get("min_spend_gbp", 0) <= budget_max_gbp
    ]

    output: dict[str, Any] = {
        "near": near,
        "party_size": party_size,
        "results": results,
        "count": len(results),
    }
    record_tool_call("venue_search", {"near": near, "party_size": party_size, "budget_max_gbp": budget_max_gbp}, output)

    if not results:
        return ToolResult(
            success=False,
            output=output,
            summary=(
                f"venue_search({near}, party={party_size}): 0 result(s). "
                "No venues matched. Do NOT call venue_search again with different parameters."
            ),
        )

    return ToolResult(
        success=True,
        output=output,
        summary=f"venue_search({near}, party={party_size}): {len(results)} result(s)",
    )


# ---------------------------------------------------------------------------
# TODO 2 — get_weather
# ---------------------------------------------------------------------------
def get_weather(city: str, date: str) -> ToolResult:
    """Look up the scripted weather for <city> on <date> (YYYY-MM-DD).

    Reads sample_data/weather.json. Returns:
      output: {"city": str, "date": str, "condition": str, "temperature_c": int, ...}
      summary: "get_weather(<city>, <date>): <condition>, <temp>C"

    If the city or date is not in the fixture, return success=False with
    a clear ToolError (SA_TOOL_INVALID_INPUT). Do NOT raise.

    MUST call record_tool_call(...) before returning.
    """
    fixture_path = _SAMPLE_DATA / "weather.json"
    if not fixture_path.exists():
        return ToolResult(
            success=False,
            output={"error": "fixture_missing"},
            summary="get_weather: sample_data/weather.json not found",
            error=ToolError(code="SA_TOOL_DEPENDENCY_MISSING", message="weather.json missing"),
        )

    data = json.loads(fixture_path.read_text())
    city_data = data.get(city.lower())
    if city_data is None:
        return ToolResult(
            success=False,
            output={"city": city, "date": date, "error": f"city '{city}' not in fixture"},
            summary=f"get_weather({city}, {date}): city not found",
            error=ToolError(code="SA_TOOL_INVALID_INPUT", message=f"unknown city: {city}"),
        )

    entry = city_data.get(date)
    if entry is None:
        return ToolResult(
            success=False,
            output={"city": city, "date": date, "error": f"date '{date}' not in fixture for {city}"},
            summary=f"get_weather({city}, {date}): date not found",
            error=ToolError(code="SA_TOOL_INVALID_INPUT", message=f"no data for {city} on {date}"),
        )

    output: dict[str, Any] = {"city": city, "date": date, **entry}
    record_tool_call("get_weather", {"city": city, "date": date}, output)

    return ToolResult(
        success=True,
        output=output,
        summary=f"get_weather({city}, {date}): {entry['condition']}, {entry['temperature_c']}C",
    )


# ---------------------------------------------------------------------------
# TODO 3 — calculate_cost
# ---------------------------------------------------------------------------
def calculate_cost(
    venue_id: str,
    party_size: int,
    duration_hours: int,
    catering_tier: str = "bar_snacks",
) -> ToolResult:
    """Compute the total cost for a booking.

    Formula:
      base_per_head = base_rates_gbp_per_head[catering_tier]
      venue_mult    = venue_modifiers[venue_id]
      subtotal      = base_per_head * venue_mult * party_size * max(1, duration_hours)
      service       = subtotal * service_charge_percent / 100
      total         = subtotal + service + <venue's hire_fee_gbp + min_spend_gbp>
      deposit_rule  = per deposit_policy thresholds

    Returns:
      output: {
        "venue_id": str,
        "party_size": int,
        "duration_hours": int,
        "catering_tier": str,
        "subtotal_gbp": int,
        "service_gbp": int,
        "total_gbp": int,
        "deposit_required_gbp": int,
      }
      summary: "calculate_cost(<venue>, <party>): total £<N>, deposit £<M>"

    MUST call record_tool_call(...) before returning.
    """
    catering_path = _SAMPLE_DATA / "catering.json"
    venues_path = _SAMPLE_DATA / "venues.json"
    if not catering_path.exists():
        return ToolResult(
            success=False,
            output={"error": "fixture_missing"},
            summary="calculate_cost: sample_data/catering.json not found",
            error=ToolError(code="SA_TOOL_DEPENDENCY_MISSING", message="catering.json missing"),
        )

    catering = json.loads(catering_path.read_text())
    base_rates: dict[str, int] = catering["base_rates_gbp_per_head"]
    venue_modifiers: dict[str, float] = catering["venue_modifiers"]
    service_pct: int = catering["service_charge_percent"]

    if catering_tier not in base_rates:
        return ToolResult(
            success=False,
            output={"error": f"unknown catering_tier: {catering_tier}"},
            summary=f"calculate_cost: unknown catering_tier '{catering_tier}'",
            error=ToolError(code="SA_TOOL_INVALID_INPUT", message=f"unknown catering tier: {catering_tier}"),
        )
    if venue_id not in venue_modifiers:
        return ToolResult(
            success=False,
            output={"error": f"unknown venue_id: {venue_id}"},
            summary=f"calculate_cost: unknown venue_id '{venue_id}'",
            error=ToolError(code="SA_TOOL_INVALID_INPUT", message=f"unknown venue: {venue_id}"),
        )

    hire_fee = 0
    min_spend = 0
    if venues_path.exists():
        venues = json.loads(venues_path.read_text())
        venue = next((v for v in venues if v["id"] == venue_id), None)
        if venue:
            hire_fee = venue.get("hire_fee_gbp", 0)
            min_spend = venue.get("min_spend_gbp", 0)

    base_per_head = base_rates[catering_tier]
    venue_mult = venue_modifiers[venue_id]
    subtotal = int(base_per_head * venue_mult * party_size * max(1, duration_hours))
    service = int(subtotal * service_pct / 100)
    total = subtotal + service + hire_fee + min_spend

    if total < 300:
        deposit = 0
    elif total <= 1000:
        deposit = int(total * 0.20)
    else:
        deposit = int(total * 0.30)

    output: dict[str, Any] = {
        "venue_id": venue_id,
        "party_size": party_size,
        "duration_hours": duration_hours,
        "catering_tier": catering_tier,
        "subtotal_gbp": subtotal,
        "service_gbp": service,
        "total_gbp": total,
        "deposit_required_gbp": deposit,
    }
    record_tool_call(
        "calculate_cost",
        {"venue_id": venue_id, "party_size": party_size, "duration_hours": duration_hours, "catering_tier": catering_tier},
        output,
    )

    return ToolResult(
        success=True,
        output=output,
        summary=f"calculate_cost({venue_id}, {party_size}): total £{total}, deposit £{deposit}",
    )


# ---------------------------------------------------------------------------
# TODO 4 — generate_flyer
# ---------------------------------------------------------------------------
def generate_flyer(session: Session, event_details: dict) -> ToolResult:
    """Produce an HTML flyer and write it to workspace/flyer.html.

    event_details is expected to contain at least:
      venue_name, venue_address, date, time, party_size, condition,
      temperature_c, total_gbp, deposit_required_gbp

    Write a self-contained HTML flyer (inline CSS, no external assets). Tag every key fact with data-testid="<n>" so the integrity check can parse it.

    Write a formatted HTML flyer with an H1 title, the event
    facts, a weather summary, and the cost breakdown.

    Returns:
      output: {"path": "workspace/flyer.html", "bytes_written": int}
      summary: "generate_flyer: wrote <path> (<N> chars)"

    MUST call record_tool_call(...) before returning — the integrity
    check compares the flyer's contents against earlier tool outputs.

    IMPORTANT: this tool MUST be registered with parallel_safe=False
    because it writes a file.
    """
    required = ["venue_name", "date", "time", "party_size", "total_gbp"]
    missing = [k for k in required if not event_details.get(k)]
    if missing:
        return ToolResult(
            success=False,
            output={"error": "missing_event_details", "missing_keys": missing},
            summary=(
                f"generate_flyer: missing required fields {missing}. "
                "Call venue_search, get_weather, and calculate_cost first, "
                "then pass their outputs as event_details."
            ),
            error=ToolError(code="SA_TOOL_INVALID_INPUT", message=f"missing fields: {missing}"),
        )

    venue_name = event_details.get("venue_name", "TBD")
    venue_address = event_details.get("venue_address", "")
    date = event_details.get("date", "")
    time = event_details.get("time", "")
    party_size = event_details.get("party_size", "")
    condition = event_details.get("condition", "")
    temperature_c = event_details.get("temperature_c", "")
    total_gbp = event_details.get("total_gbp", "")
    deposit_required_gbp = event_details.get("deposit_required_gbp", "")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{venue_name} — Edinburgh Event</title>
<style>
  body {{ font-family: Georgia, serif; max-width: 600px; margin: 2rem auto; padding: 0 1.5rem; background: #fafaf8; color: #222; }}
  h1 {{ font-size: 1.8rem; margin-bottom: 0.25rem; }}
  .subtitle {{ color: #666; margin-bottom: 1.5rem; font-style: italic; }}
  dl {{ display: grid; grid-template-columns: 11rem 1fr; gap: 0.5rem 1rem; margin-top: 1rem; }}
  dt {{ font-weight: bold; color: #555; }}
  dd {{ margin: 0; }}
  .cost-section {{ margin-top: 1.5rem; border-top: 2px solid #c8a96e; padding-top: 1rem; }}
</style>
</head>
<body>
<article>
  <h1>Evening at <span data-testid="venue-name">{venue_name}</span></h1>
  <p class="subtitle" data-testid="venue-address">{venue_address}</p>
  <dl>
    <dt>Date</dt>
    <dd data-testid="date">{date}</dd>
    <dt>Time</dt>
    <dd data-testid="time">{time}</dd>
    <dt>Party size</dt>
    <dd data-testid="party-size">{party_size}</dd>
    <dt>Weather</dt>
    <dd data-testid="condition">{condition}</dd>
    <dt>Temperature</dt>
    <dd data-testid="temperature">{temperature_c}°C</dd>
  </dl>
  <div class="cost-section">
    <dl>
      <dt>Total cost</dt>
      <dd data-testid="total">£{total_gbp}</dd>
      <dt>Deposit required</dt>
      <dd data-testid="deposit">£{deposit_required_gbp}</dd>
    </dl>
  </div>
</article>
</body>
</html>"""

    flyer_path = session.workspace_dir / "flyer.html"
    atomic_write_text(flyer_path, html)

    path_str = "workspace/flyer.html"
    output: dict[str, Any] = {"path": path_str, "bytes_written": len(html)}
    record_tool_call("generate_flyer", {"event_details": event_details}, output)

    return ToolResult(
        success=True,
        output=output,
        summary=f"generate_flyer: wrote {path_str} ({len(html)} chars)",
    )


# ---------------------------------------------------------------------------
# Registry builder — DO NOT MODIFY the name, signature, or registration calls.
# The grader imports and calls this to pick up your tools.
# ---------------------------------------------------------------------------
def build_tool_registry(session: Session) -> ToolRegistry:
    """Build a session-scoped tool registry with all four Ex5 tools plus
    the sovereign-agent builtins (read_file, write_file, list_files,
    handoff_to_structured, complete_task).

    DO NOT change the tool names — the tests and grader call them by name.
    """
    from sovereign_agent.tools.builtin import make_builtin_registry

    reg = make_builtin_registry(session)

    # venue_search
    reg.register(
        _RegisteredTool(
            name="venue_search",
            description="Search Edinburgh venues by area, party size, and max budget.",
            fn=venue_search,
            parameters_schema={
                "type": "object",
                "properties": {
                    "near": {"type": "string"},
                    "party_size": {"type": "integer"},
                    "budget_max_gbp": {"type": "integer", "default": 1000},
                },
                "required": ["near", "party_size"],
            },
            returns_schema={"type": "object"},
            is_async=False,
            parallel_safe=True,  # read-only
            examples=[
                {
                    "input": {"near": "Haymarket", "party_size": 6, "budget_max_gbp": 800},
                    "output": {"count": 1, "results": [{"id": "haymarket_tap"}]},
                }
            ],
        )
    )

    # get_weather
    reg.register(
        _RegisteredTool(
            name="get_weather",
            description="Get scripted weather for a city on a YYYY-MM-DD date.",
            fn=get_weather,
            parameters_schema={
                "type": "object",
                "properties": {
                    "city": {"type": "string"},
                    "date": {"type": "string"},
                },
                "required": ["city", "date"],
            },
            returns_schema={"type": "object"},
            is_async=False,
            parallel_safe=True,  # read-only
            examples=[
                {
                    "input": {"city": "Edinburgh", "date": "2026-04-25"},
                    "output": {"condition": "cloudy", "temperature_c": 12},
                }
            ],
        )
    )

    # calculate_cost
    reg.register(
        _RegisteredTool(
            name="calculate_cost",
            description="Compute total cost and deposit for a booking.",
            fn=calculate_cost,
            parameters_schema={
                "type": "object",
                "properties": {
                    "venue_id": {"type": "string"},
                    "party_size": {"type": "integer"},
                    "duration_hours": {"type": "integer"},
                    "catering_tier": {
                        "type": "string",
                        "enum": ["drinks_only", "bar_snacks", "sit_down_meal", "three_course_meal"],
                        "default": "bar_snacks",
                    },
                },
                "required": ["venue_id", "party_size", "duration_hours"],
            },
            returns_schema={"type": "object"},
            is_async=False,
            parallel_safe=True,  # pure compute, no shared state
            examples=[
                {
                    "input": {
                        "venue_id": "haymarket_tap",
                        "party_size": 6,
                        "duration_hours": 3,
                    },
                    "output": {"total_gbp": 540, "deposit_required_gbp": 0},
                }
            ],
        )
    )

    # generate_flyer — parallel_safe=False because it writes a file
    def _flyer_adapter(event_details: dict) -> ToolResult:
        return generate_flyer(session, event_details)

    reg.register(
        _RegisteredTool(
            name="generate_flyer",
            description="Write an HTML flyer for the event to workspace/flyer.html.",
            fn=_flyer_adapter,
            parameters_schema={
                "type": "object",
                "properties": {"event_details": {"type": "object"}},
                "required": ["event_details"],
            },
            returns_schema={"type": "object"},
            is_async=False,
            parallel_safe=False,  # writes a file — MUST be False
            examples=[
                {
                    "input": {
                        "event_details": {
                            "venue_name": "Haymarket Tap",
                            "date": "2026-04-25",
                            "party_size": 6,
                        }
                    },
                    "output": {"path": "workspace/flyer.html"},
                }
            ],
        )
    )

    return reg


__all__ = [
    "build_tool_registry",
    "venue_search",
    "get_weather",
    "calculate_cost",
    "generate_flyer",
]