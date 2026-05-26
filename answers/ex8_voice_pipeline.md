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

I ran Ex8 in text mode; every trace event has `"mode": "text"`.

Conversation state lives in `ManagerPersona.history`, a plain Python
list of `ManagerTurn` objects. Each turn stores the user's utterance and
Alasdair's reply. On every `respond()` call, `_build_messages()` sends
the fixed system prompt first, then replays the whole history as
alternating `user` and `assistant` messages, and finally appends the new
utterance. So the model sees the full conversation each time. The live
state is only in memory. The trace file logs each utterance, which is
enough for audit or reconstruction, but a crashed process would not
resume `ManagerPersona.history` automatically.

The persona mostly stays in character through a narrow system prompt
and `temperature=0.0`. The prompt gives the manager a name, style, word
limit, and the exact booking rules: accept up to 8 guests unless the
deposit is above £300, decline 9 or more, and name alternatives. The
run shows that working. When I typed `239`, the manager replied that the
party was too large and suggested The Royal Oak or Bennet's Bar, while
still using short Edinburgh-flavoured phrasing.

I did not run real voice mode. The first voice failure I would expect is
bad turn-taking from the recorder. `_record_until_silence` uses a fixed
RMS threshold of 500 to decide whether the user has stopped speaking.
In a noisy pub, background music or chatter could keep the RMS above
that threshold, so the loop would wait until the 15-second hard cap
instead of stopping after 2 seconds of silence. I would replace the
fixed amplitude gate with an adaptive threshold from a short ambient
calibration window, or use a real VAD such as WebRTC VAD or Silero.

## Citations

- `homework/ex8/sess_626db8fccb11/logs/trace.jsonl:1` — `voice.utterance_in` (turn 0, user says "Hello"), confirming the pipeline captured and logged input correctly in text mode
- `homework/ex8/sess_626db8fccb11/logs/trace.jsonl:6` — `voice.utterance_out` "Too big, I'm afraid. We cannae handle parties o' that size. Try The Royal Oak or Bennet's Bar." — manager rejects party of 239, names the rule-specified alternatives, uses "cannae" and "o'" in-character
