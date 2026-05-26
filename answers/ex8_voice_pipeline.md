# Ex8 — Voice pipeline

## Prompt

Describe how your voice pipeline handles state across STT → LLM → TTS turns.
Where does the conversation history live? How does the Llama-3.3-70B manager
persona stay in character? If you ran in voice mode (not just text), describe
one failure mode you observed with real audio (latency, transcription errors,
audio quality) and how you'd address it.

If you only ran in text mode, answer the state question, the persona question,
and describe ONE plausible failure mode you'd expect from voice even without
having tested it. (Full credit still possible.)

**Word count:** 200-400 words.

## Your answer

*(Write your answer below this line. Do not remove the heading.)*

---

I ran in text mode (trace shows `"mode": "text"` throughout).

**Conversation state.** State lives entirely in
`ManagerPersona.history` — a Python list of `ManagerTurn` objects, each
holding `user_utterance` + `manager_response`. On every `respond()`
call, `_build_messages()` prepends the fixed system prompt and then
replays the full history as alternating `user`/`assistant` messages
before appending the new utterance. The model therefore sees the
complete conversation on every call. This is in-process, in-RAM storage:
it is NOT written to disk. The session's `trace.jsonl` records every
turn's text verbatim, so the conversation is recoverable from logs, but
if the process crashes mid-session the live `history` is gone and the
persona would restart without context.

**Persona.** `ManagerPersona` uses `temperature=0.0`, which makes the
model deterministic: the same conversation history always produces the
same reply. The system prompt locks in the character (Alasdair MacLeod,
blunt, Scots expressions, 60-word limit) and explicitly enumerates the
booking rules. The model enforces them without deviation — turn 2 in the
trace shows a party-of-239 request being rejected with "Too big, I'm
afraid. We cannae handle parties o' that size. Try The Royal Oak or
Bennet's Bar." The alternatives are named directly from the system prompt
rules, confirming the model is grounding decisions in the prompt rather
than improvising.

**Plausible voice failure mode.** The silence detector in
`_record_until_silence` uses a fixed RMS threshold of 500 (int16 scale)
to decide when a user has stopped speaking. In a noisy environment —
which a pub almost certainly is — ambient noise (music, crowd chatter)
keeps RMS above that threshold continuously. The silence condition never
triggers, so every turn runs until the hard cap of `MAX_UTTERANCE_S = 15
seconds`. The user hears no response for up to 15 seconds, not the
expected 2-second turnaround. The fix is an adaptive threshold that
calibrates against the first 0.5 seconds of ambient noise before the
user speaks, or replacing the amplitude gate with a proper VAD model
(WebRTC VAD or Silero) that distinguishes speech from background noise.

## Citations

- `homework/ex8/sess_626db8fccb11/logs/trace.jsonl:1` — `voice.utterance_in` (turn 0, user says "Hello"), confirming the pipeline captured and logged input correctly in text mode
- `homework/ex8/sess_626db8fccb11/logs/trace.jsonl:6` — `voice.utterance_out` "Too big, I'm afraid. We cannae handle parties o' that size. Try The Royal Oak or Bennet's Bar." — manager rejects party of 239, names the rule-specified alternatives, uses "cannae" and "o'" in-character
