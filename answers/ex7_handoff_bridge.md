# Ex7 — Handoff bridge

## Prompt

Walk through the bidirectional round-trip your handoff bridge performs. Start
with the initial task, describe each handoff event (forward and reverse), and
explain what session state the system is in at each transition. Identify the
exact line in your logs where the second research cycle begins after the
structured half's first rejection.

**Word count:** 200-400 words.

## Your answer

*(Write your answer below this line. Do not remove the heading.)*

---

**Initial task.** The task is "Book a venue for 12 people in Haymarket, Friday 19:30." The session starts
in loop state; the bridge emits `bridge.round_start` (round=1) and
invokes the loop half.

**Round 1 — loop running.** The planner produces 4 subgoals. The
executor calls `venue_search(near='Haymarket', party_size=12,
budget_max_gbp=2000)`, which immediately fails: party_size=12 exceeds
the auto-booking maximum of 8. Rather than retrying, the executor calls
`handoff_to_structured` with `data={"error": "party_size_exceeds_max",
"requested_party_size": 12, "max_allowed": 8}` and returns
`next_action="handoff_to_structured"`.

**Forward handoff.** The bridge calls `build_forward_handoff`, packages
the loop result into a `Handoff` object, writes it to
`ipc/handoff_to_structured.json`, and emits
`session.state_changed(from=loop, to=structured, round=1)` (trace
line 6). Session state is now "structured half running."

**Structured half rejection.** `RasaStructuredHalf.run()` passes the
handoff data to `normalise_booking_payload`. Because the data dict
contains no `venue_id` key, `normalise_booking_payload` raises
`ValidationFailed("missing venue_id")`, which `run()` catches and
returns as `HalfResult(success=False, next_action="escalate",
summary="normalisation failed: missing venue_id")`.

**Reverse handoff.** The bridge detects `next_action="escalate"`, calls
`build_reverse_task` to compose a new task dict that embeds the
rejection reason (`"normalisation failed: missing venue_id"`) and
`retry=True` alongside the original task context. It archives the stale
forward-handoff file into `logs/handoffs/round_1_forward.json` (instead
of deleting it, preserving the audit trail), and emits
`session.state_changed(from=structured, to=loop, round=1,
rejection_reason="normalisation failed: missing venue_id")` (trace
line 7). Session state returns to "loop half."

**Second research cycle begins.** Trace line 8 —
`bridge.round_start(round=2, half=loop)` — is the exact event where
round 2 starts. The loop half receives the new reverse-task dict and
the planner replans from scratch. This round also fails to find a
venue and escalates again; after three rounds the bridge exhausts
`max_rounds=3` and marks the session failed.

## Citations

- `examples/ex7-handoff-bridge/sess_8403bd4eb9c8/logs/trace.jsonl:6` — `session.state_changed` loop→structured (round=1 forward handoff written)
- `examples/ex7-handoff-bridge/sess_8403bd4eb9c8/logs/trace.jsonl:7` — `session.state_changed` structured→loop (round=1 rejection, reason="normalisation failed: missing venue_id")
- `examples/ex7-handoff-bridge/sess_8403bd4eb9c8/logs/trace.jsonl:8` — `bridge.round_start` round=2, the exact line where the second research cycle begins
