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

The executor then made the expected five tool calls. First it called
`venue_search(near='Haymarket', party_size=6, budget_max_gbp=800)`,
which returned Haymarket Tap. In the same executor step it also called
`get_weather(city='edinburgh', date='2026-04-25')` and
`calculate_cost(venue_id='haymarket_tap', party_size=6,
duration_hours=3, catering_tier='bar_snacks')`. Those three calls are
read-only and registered as `parallel_safe=True`. The next step called
`generate_flyer`, which writes `workspace/flyer.html`, so its
registration is correctly `parallel_safe=False`. The final call was
`complete_task`.

Step-by-step verification showed one awkward detail: `calculate_cost`
returned total £556 and deposit £111, while the scripted
`generate_flyer` call used `total_gbp: 540` and
`deposit_required_gbp: 0`. The current integrity checker does not flag
that mismatch, because `fact_appears_in_log` accepts facts found in
tool arguments as well as tool outputs. It does catch values that appear
only in the final flyer. In `sess_6b3d51602f58`, the flyer was edited
to show `£9999`; that number is absent from the tool log, so
`verify_dataflow` returns `ok=False` with `unverified_facts=["£9999"]`.
After rerunning the offline scenario, the normal flyer passed with four
verified facts.

## Citations

- `examples/ex5-edinburgh-research/sess_52b043e62444/logs/trace.jsonl:2` — planner produced 2 subgoals
- `examples/ex5-edinburgh-research/sess_52b043e62444/logs/trace.jsonl:3` — `venue_search` for Haymarket party of 6
- `examples/ex5-edinburgh-research/sess_52b043e62444/logs/trace.jsonl:5` — `calculate_cost` returning £556/£111
- `examples/ex5-edinburgh-research/sess_6b3d51602f58/workspace/flyer.html:35` — planted `£9999` value that the checker flags
