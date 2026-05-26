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

The offline run starts with `book for party of 12 in Haymarket`.
Trace line 1 is the bridge entering round 1 in the loop half. The first
planner ticket produces one loop subgoal, and the executor calls
`venue_search(near='Haymarket', party_size=12, budget_max_gbp=2000)`.
That tool refuses the search because the auto-booking cap is 8, but the
scripted executor still sends the intended first proposal onward:
`handoff_to_structured` carries Haymarket Tap, the date
`2026-04-25`, time `19:30`, party size `12`, and deposit `£0`.

The bridge wraps that loop result in a `Handoff`, writes
`ipc/handoff_to_structured.json`, and records
`session.state_changed` from loop to structured at trace line 6. Rasa
normalises the payload, sees `party_size=12`, and rejects it with
`party_too_large`. The bridge records the reverse transition at trace
line 7, including the rejection reason: "sorry, we can't accept this
booking. reason: party_too_large". The live IPC directory ends with a
single `handoff_to_structured.json`, so there is no pile-up of forward
handoff files across the retry.

The second research cycle begins exactly at trace line 8:
`bridge.round_start(round=2, half=loop)`. The new task includes the
rejection reason and `retry=True`, so the loop half replans. This time
the executor searches `Old Town` for party size 6, gets one result, and
hands off The Royal Oak with `party_size="6"` and deposit `£0`. The
bridge records the second loop-to-structured transition at line 13.
Rasa accepts the normalised booking, and trace line 14 records
`session.state_changed` from structured to complete. The bridge exits
with outcome `completed` after 2 rounds.

## Citations

- `examples/ex7-handoff-bridge/sess_298116815c48/logs/trace.jsonl:6` — first loop→structured transition
- `examples/ex7-handoff-bridge/sess_298116815c48/logs/trace.jsonl:7` — structured→loop transition with `party_too_large`
- `examples/ex7-handoff-bridge/sess_298116815c48/logs/trace.jsonl:8` — exact start of the second research cycle
- `examples/ex7-handoff-bridge/sess_298116815c48/logs/trace.jsonl:14` — structured→complete transition
