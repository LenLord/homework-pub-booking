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

**Input dict → Rasa payload.**
`RasaStructuredHalf.run()` receives `input_payload["data"]` and hands it
to `normalise_booking_payload()` in `validator.py`. That function runs
five field-level normalisers: `canonicalise_venue_id` lowercases and
replaces whitespace/hyphens with underscores ("Haymarket Tap" →
"haymarket_tap"); `_normalise_date` handles ISO-8601 passthrough, the
literals "today"/"tomorrow", and natural-language ordinals ("25th April
2026" → "2026-04-25"); `parse_time_24h` accepts both 12-hour ("7:30pm")
and 24-hour ("19:30") strings; `parse_party_size` strips trailing words
("6 people" → 6) and rejects values < 1; `parse_currency_gbp` strips
"£" and "GBP" suffixes and returns an int. Any unrecoverable input raises
`ValidationFailed`, which `run()` catches and returns as a
`HalfResult(success=False, next_action="escalate")`. Clean data is
assembled into `{"sender": "homework-<sha1[:8]>", "message":
"/confirm_booking", "metadata": {"booking": {...}}}` where the sender is
a SHA-1 hash of `venue_id-date-time`, making retries idempotent within
one booking slot.

**ActionValidateBooking → HalfResult.**
The CALM flow (`data/flows.yml`) triggers `action_validate_booking` on
receiving `/confirm_booking`. The action reads
`tracker.latest_message.metadata.booking` — the same dict we posted —
explicitly sets all booking fields as Rasa slots, then applies two rule
checks: `party_size > 8` → `SlotSet("validation_error", "party_too_large")`
and `deposit_gbp > 300` → `SlotSet("validation_error", "deposit_too_high")`.
Missing required fields each produce `SlotSet("validation_error",
"missing_<field>")`. On success it emits `SlotSet("booking_reference",
"BK-<sha1[:8]>")` and clears `validation_error`. The CALM flow then
branches: failure utters `utter_booking_rejected`, success utters
`utter_booking_confirmed`. `RasaStructuredHalf.run()` reads the response
messages: `custom.action == "committed"` → `HalfResult(success=True,
next_action="complete")`; `custom.action == "rejected"` →
`HalfResult(success=False, next_action="escalate")`.

**Production change.**
The response parser falls back to string matching (`"booking confirmed"
in text`, `"can't accept" in text`) alongside the structured `custom`
dict. A template change by a non-engineer silently breaks this without
any test failure, because the `custom` dict remains correct while the
text branch produces stale decisions. For production I would remove
the text-matching entirely and require `custom.action` to be present,
surfacing a clear error when it is absent rather than silently
misclassifying the response.

## Citations

- `examples/ex6-rasa-half/sess_13fc28146ebc/logs/trace.jsonl:1` — `structured.dispatch` event showing raw (pre-normalisation) input posted to the Rasa webhook: `venue_id="Haymarket Tap"`, `date="25th April 2026"`, `time="7:30pm"`, `party_size="6"`
- `examples/ex6-rasa-half/sess_13fc28146ebc/logs/trace.jsonl:2` — `structured.result` event confirming the custom action returned `custom.action="committed"` and `booking_reference="BK-7D401E9E"`, which `RasaStructuredHalf.run()` translated to `HalfResult(success=True, next_action="complete")`
- `examples/ex6-rasa-half/sess_13fc28146ebc/workspace/booking_result.json` — full normalised booking artifact written to workspace, showing `venue_id="haymarket_tap"`, `date="2026-04-25"`, `time="19:30"`, `party_size=6` (int)
