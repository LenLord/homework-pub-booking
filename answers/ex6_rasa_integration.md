# Ex6 — Rasa integration

## Prompt

How did you wire Rasa CALM into the sovereign-agent `StructuredHalf` protocol?
Describe specifically: (1) how your subclass translates an input `dict` into a
Rasa-compatible intent payload, (2) how your `ActionValidateBooking` custom
action surfaces validation failures back into a `HalfResult`, and (3) one thing
you would change about the integration if you were building this for production.

**Word count:** 200-400 words.

## Your answer

*(Write your answer below this line. Do not remove the heading.)*

---

`RasaStructuredHalf.run()` takes `input_payload["data"]` and normalises
it before it ever touches Rasa. The normaliser turns human-ish values
into the shape the webhook expects: `"Haymarket Tap"` becomes
`"haymarket_tap"`, `"25th April 2026"` becomes `"2026-04-25"`,
`"7:30pm"` becomes `"19:30"`, `"6"` or `"6 people"` becomes integer
`6`, and `"£200"` becomes integer `200` in `deposit_gbp`. If one of the
required fields is missing, `ValidationFailed` is caught and returned as
`HalfResult(success=False, next_action="escalate")`; the bridge does not
crash on bad handoff data.

For valid input, the half posts a Rasa REST body like
`{"sender": "homework-<sha1>", "message": "/confirm_booking",
"metadata": {"booking": {...}}}`. The sender hash is based on
venue/date/time, so repeated attempts for the same booking slot reuse a
stable sender id.

Inside Rasa, the `confirm_booking` flow runs `action_validate_booking`.
That action reads `tracker.latest_message.metadata.booking`, writes the
booking fields into slots, and then applies the two policy checks:
party size over 8 sets `validation_error` to `party_too_large`, and
deposit over £300 sets it to `deposit_too_high`. Missing fields get
`missing_<field>`. If the booking is valid, the action clears
`validation_error` and sets a deterministic `booking_reference`. The
flow then utters either `utter_booking_rejected` or
`utter_booking_confirmed`.

Back in Python, `RasaStructuredHalf.run()` parses the webhook response.
The mock server returns a useful `custom.action`, while the real Rasa
domain currently returns plain text, so the parser accepts both:
`committed` or "booking confirmed" maps to
`HalfResult(success=True, next_action="complete")`; `rejected` or
"can't accept" maps to `next_action="escalate"`.

For production, I would make that response contract structured instead
of relying on template text. A small custom output action, or a channel
adapter that always includes `custom.action`, would let the Python half
fail loudly when the contract is missing instead of guessing from copy
that someone might edit later.

## Citations

- `examples/ex6-rasa-half/sess_13fc28146ebc/logs/trace.jsonl:1` — raw input before normalisation: `venue_id="Haymarket Tap"`, `date="25th April 2026"`, `time="7:30pm"`, `party_size="6"`
- `examples/ex6-rasa-half/sess_13fc28146ebc/logs/trace.jsonl:2` — `structured.result` showing `next_action="complete"` and booking reference `BK-7D401E9E`
- `examples/ex6-rasa-half/sess_13fc28146ebc/workspace/booking_result.json` — full normalised booking artifact written to workspace, showing `venue_id="haymarket_tap"`, `date="2026-04-25"`, `time="19:30"`, `party_size=6` (int)
