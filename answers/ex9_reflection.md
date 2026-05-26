# Ex9 — Reflection

Answer all three questions. The grader expects every question to be answered;
blank answers are zero.

---

## Q1 — Planner handoff decision

### Prompt

Find a point in your Ex7 logs where the planner decided to hand off to the
structured half. Quote the planner's reasoning or the specific subgoal's
`assigned_half` field. What signal caused the decision?

**Word count:** 100-250 words.

### Your answer

In the first planning cycle of the ex7 session, ticket `tk_3cb8743b`
produced four subgoals. The second subgoal reads:

```json
{
  "id": "sg_2",
  "description": "Hand off the chosen venue's booking data to structured process",
  "success_criterion": "Booking confirmed or rejection received",
  "estimated_tool_calls": 1,
  "assigned_half": "structured"
}
```

The signal that caused `assigned_half: "structured"` was the task
description itself: "Book a venue for 12 people in Haymarket." The
planner inferred from the party size (12 > 8 auto-booking max) that the
booking step cannot be handled autonomously by the loop half — it
requires the structured validation flow (Rasa CALM) to confirm or
reject. The planner also produced `sg_4` with `assigned_half:
"structured"` in anticipation of a possible first rejection and a
second attempt, showing it reasoned ahead about the full round-trip
topology before any tool call ran.

The loop half executed `venue_search` first (sg_1), which immediately
failed on party_size=12. Rather than following the planner's subgoal
map, the executor called `handoff_to_structured` directly with the
error data — a divergence from the plan that the bridge then handled
through its own round logic.

### Citation (required)

- `examples/ex7-handoff-bridge/sess_8403bd4eb9c8/logs/tickets/tk_3cb8743b/raw_output.json` — planner output for round 1, showing sg_2 and sg_4 with `assigned_half: "structured"` planned upfront

---

## Q2 — Dataflow integrity catch

### Prompt

Describe one instance where your Ex5 dataflow integrity check caught something
manual inspection would have missed, OR (if the check never triggered in your
runs) describe a plausible scenario where it WOULD catch a failure. Your
scenario must be specific enough that someone else could construct the test
case.

**Word count:** 100-250 words.

### Your answer

In session `sess_6b3d51602f58`, `calculate_cost` returned
`total £556, deposit £111` (trace line 5), but the executor called
`generate_flyer` with `total_gbp: 540, deposit_required_gbp: 0` (trace
line 6) — fabricated values. The grader then planted `£9999` as the
total in the rendered HTML to test the check. `verify_dataflow` extracts
all `£<N>` patterns from the flyer via regex (after stripping HTML tags)
and calls `fact_appears_in_log` for each. `£9999` appears in neither any
tool output nor any tool argument anywhere in the session log, so it
fails immediately and `verify_dataflow` returns `ok=False` with
`unverified_facts=["£9999"]`.

A manual reviewer skimming the HTML would see `£9999` in a
`<dd data-testid="total">` cell and dismiss it as a plausible-looking
large number — particularly if they already knew the booking was for six
people at a city-centre venue where £9999 could be mistaken for a
realistic group rate. The integrity check has no such bias; it simply
asks "did any tool return or receive this number?" and it did not.

To construct the test case: run the scenario with `calculate_cost`
returning `total: 556`, then monkey-patch `generate_flyer` to write a
file containing `£9999` as the total. Call `verify_dataflow` on the
file content. Assert `result.ok == False` and `"£9999" in
result.unverified_facts`.

### Citation (required)

- `examples/ex5-edinburgh-research/sess_6b3d51602f58/logs/trace.jsonl:5` — `calculate_cost` returning £556/£111
- `examples/ex5-edinburgh-research/sess_6b3d51602f58/workspace/flyer.html` — HTML with grader-planted `£9999` that the check flags

---

## Q3 — First production failure + primitive

### Prompt

If you were shipping this agent to a real pub-booking business next week,
what's the first production failure you'd expect, and which sovereign-agent
primitive (ticket state machine, manifest discipline, IPC atomic rename,
SessionQueue retry, drift-corrected scheduler, mount allowlist, HITL approval,
etc.) would surface it?

Name EXACTLY ONE primitive and EXACTLY ONE failure mode. Vague answers that
name multiple primitives or generic "something will break" failures lose
points.

**Word count:** 100-250 words.

### Your answer

**Primitive: HITL approval.**

**Failure mode:** The LLM executor fabricates a cost figure when calling
`handoff_to_structured`. The real `calculate_cost` returned `£556`, but
the executor passes `deposit_gbp: 200` (a plausible-looking value the
LLM chose without grounding it in the tool output). Rasa accepts the
booking at £200 deposit. The pub expects £556 on arrival; the customer
paid for £200. The discrepancy surfaces only at the venue on the day of
the event — too late to recover without a refund dispute.

`verify_dataflow` does not catch this: `200` appears in the executor's
`handoff_to_structured` arguments, so `fact_appears_in_log` returns
`True` for it. The check confirms the value was in the session log; it
cannot verify it came from the right tool.

HITL approval on the `handoff_to_structured` tool call would surface it.
If `requires_human_approval: true` is set for that tool, the session
pauses before the forward handoff is written. A human reviewer sees the
proposed booking dict side-by-side with the tool call log and notices
`deposit_gbp: 200` never appeared in any `calculate_cost` output. They
reject the proposal, the executor is re-prompted with the actual £556
figure, and the booking is retried with the correct amount. In the
current logs every `handoff_to_structured` call shows
`requires_human_approval: false` — that field is the exact configuration
switch to flip before shipping.

### Citation (optional but encouraged)

- `examples/ex7-handoff-bridge/sess_8403bd4eb9c8/logs/tickets/tk_7f8c234a/raw_output.json` — `handoff_to_structured` tool call with `requires_human_approval: false`; this is the field that must be `true` in production to surface the fabricated-cost failure
