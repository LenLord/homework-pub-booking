# Ex5 — Edinburgh research loop scenario

## Prompt

Describe the trajectory your Ex5 scenario takes through the loop half. Which
subgoals did the planner produce? Which tools were called? Were there any
tool calls that the dataflow integrity check would have flagged if you had
left them uncorrected?

**Word count:** 150-300 words.

## Your answer

*(Write your answer below this line. Do not remove the heading.)*

---

The planner produced two subgoals, both assigned to the loop half:
sg_1 ("research Edinburgh venues near Haymarket for a party of 6") and
sg_2 ("produce an HTML flyer with the chosen venue, weather, and cost").
sg_2 depends on sg_1; the planner estimated four total tool calls.

The executor completed sg_1 in four turns with five tool calls.
Turn 1 called `venue_search(near='Haymarket', party_size=6,
budget_max_gbp=800)`, returning one result — Haymarket Tap. Still in
the same turn, `get_weather(city='edinburgh', date='2026-04-25')` and
`calculate_cost(venue_id='haymarket_tap', ...)` ran next; all three are
read-only and parallel_safe. Turn 2 called `generate_flyer`, which
writes `workspace/flyer.html` and is therefore not parallel_safe. Turn
3 called `complete_task`.

The dataflow integrity check would have flagged two issues if left
uncorrected. First, `calculate_cost` returned total £556 and deposit
£111, but `generate_flyer` was called with `total_gbp: 540` and
`deposit_required_gbp: 0` — fabricated values that never appeared in
any tool output. Second, the rendered flyer HTML contained `£9999` as
the total cost — a grader-planted value that does not appear in any
tool output or argument anywhere in the session. `verify_dataflow`
extracts money facts via regex and checks each against the full tool
call log; `£9999` fails immediately. I corrected the generate_flyer
call to pass the actual £556 and £111 from the calculate_cost output,
and the planted value in the flyer was caught and replaced.

## Citations

- `examples/ex5-edinburgh-research/sess_6b3d51602f58/logs/tickets/tk_f5c342b3/summary.md` — planner produced 2 subgoals, both assigned to loop half
- `examples/ex5-edinburgh-research/sess_6b3d51602f58/logs/trace.jsonl:5` — `executor.tool_called` for calculate_cost returning £556/£111, contrasting with line 6 where generate_flyer received fabricated £540/£0
