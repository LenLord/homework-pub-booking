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

In the real Ex7 run, the first planner ticket was `tk_3cb8743b`. It
planned four subgoals before any executor tool ran. The useful line is
the second subgoal:

```json
{
  "id": "sg_2",
  "description": "Hand off the chosen venue's booking data to structured process",
  "success_criterion": "Booking confirmed or rejection received",
  "estimated_tool_calls": 1,
  "assigned_half": "structured"
}
```

The signal was the booking-confirmation step, not just venue research.
The user asked to book for 12 people, while the structured policy caps
automatic booking at 8. The planner therefore kept the search work in
the loop half but assigned the confirmation step to the structured half,
where Rasa can approve or reject under the fixed rules. It also planned
`sg_4` as another structured handoff after a retry, so the round-trip
shape was present in the plan before the first tool call.

The executor did not follow that plan cleanly. It called
`venue_search` with party size 12, hit the cap, and then handed the
error payload to the structured half. That divergence is visible in the
trace, but the planner's intent is still clear from the `assigned_half`
field in `tk_3cb8743b`.

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

In `sess_6b3d51602f58`, the normal tool sequence ran first:
`calculate_cost` returned "total £556, deposit £111" at trace line 5.
The rendered flyer was then edited so the total cell contained `£9999`
instead. That value is visible in
`workspace/flyer.html` under `data-testid="total"`, but it never appears
in the venue, weather, cost, or flyer tool outputs.

The check catches this because `verify_dataflow` strips HTML, extracts
money facts like `£9999`, and checks each fact against the tool-call
log. When I reconstructed the run and called `verify_dataflow` on that
flyer, the result was `ok=False` with `unverified_facts=["£9999"]`.
The legitimate facts from the same flyer, such as `cloudy` and `12`,
still verified.

This is the kind of mistake a human reviewer can miss. The venue name
and weather look right, the page layout looks fine, and the bad value is
only one small `<dd>` cell. To reproduce it, run Ex5, change only the
flyer's total to `£9999`, then call `verify_dataflow` on the edited
HTML. The expected assertion is that the check fails and reports
`£9999`.

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

**Failure mode:** fabricated deposit in the forward handoff.

The failure I would expect first is the executor making up a deposit
when it calls `handoff_to_structured`. For example, the cost tool may
return one deposit amount, but the handoff payload may contain
`deposit_gbp: 200` because the model picked a plausible number while
assembling the booking dict. Rasa would see a clean-looking structured
payload and accept it. The customer would then have one deposit figure,
while the venue's real cost calculation says another.

HITL approval is the primitive I would use to surface that before the
booking leaves the loop half. If the handoff tool requires approval, the
session pauses before the forward handoff is written. A reviewer checks
the proposed booking payload against the preceding tool calls and either
approves it or rejects it for correction. The current Ex7 ticket shows
the opposite setting: the `handoff_to_structured` call has
`requires_human_approval: false`. For a real pub-booking business, that
is the switch I would flip first, because the handoff is the point where
an ungrounded number becomes an external commitment.

### Citation (optional but encouraged)

- `examples/ex7-handoff-bridge/sess_298116815c48/logs/tickets/tk_1176eeca/raw_output.json` — `handoff_to_structured` tool call with `requires_human_approval: false`; this is the field that must be `true` in production to surface the fabricated-deposit failure
