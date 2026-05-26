"""Ex8 — the pub manager persona.

Wraps a Llama-3.3-70B-Instruct model on Nebius to play an Edinburgh
pub manager. The persona is deterministic (temperature=0) and
rule-based: accepts bookings under £300 deposit and <= 8 people,
rejects otherwise with a specific reason.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sovereign_agent._internal.llm_client import (
    ChatMessage,
    LLMClient,
    OpenAICompatibleClient,
)

# TODO: if you want to tweak the persona (accent, attitude, name), edit
# here. Keep the rules section intact — the grader's judge checks that
# the manager's decisions still follow them.
MANAGER_SYSTEM_PROMPT = """\
You are Alasdair MacLeod, manager of Haymarket Tap in Edinburgh.
You are blunt and no-nonsense, but fair. Speak in short sentences;
use the occasional Scots expression. Never break character.

Booking rules you enforce:

  * Up to 8 guests: ACCEPT, unless the requested deposit exceeds £300.
  * 9 or more guests: DECLINE — the venue can't fit them. Point them
    toward The Royal Oak or Bennet's Bar instead.
  * Deposit above £300: DECLINE — that needs head-office approval,
    which you don't have.

On acceptance: confirm the date and time, then ask for a contact number.
On refusal: state the exact reason. Invent no additional rules.

Limit replies to 60 words. No emoji.
"""


@dataclass
class ManagerTurn:
    """One exchange in the manager conversation."""

    user_utterance: str
    manager_response: str


@dataclass
class ManagerPersona:
    """Wraps the LLM client with the manager's system prompt and history."""

    client: LLMClient
    model: str = "meta-llama/Llama-3.3-70B-Instruct"
    system_prompt: str = MANAGER_SYSTEM_PROMPT
    history: list[ManagerTurn] = field(default_factory=list)

    @classmethod
    def from_env(cls) -> ManagerPersona:
        """Build a ManagerPersona using NEBIUS_KEY from the environment."""
        client = OpenAICompatibleClient(
            base_url="https://api.tokenfactory.nebius.com/v1/",
            api_key_env="NEBIUS_KEY",
        )
        return cls(client=client)

    async def respond(self, utterance: str) -> str:
        """Send one user utterance, get the manager's reply back."""
        msg_list = self._build_messages(utterance)
        resp = await self.client.chat(
            model=self.model,
            messages=msg_list,
            temperature=0.0,
            max_tokens=180,
        )
        response = (resp.content or "").strip()
        self.history.append(ManagerTurn(user_utterance=utterance, manager_response=response))
        return response

    def _build_messages(self, utterance: str) -> list[ChatMessage]:
        """System prompt + full turn history + incoming utterance."""
        msg_list: list[ChatMessage] = [ChatMessage(role="system", content=self.system_prompt)]
        for turn in self.history:
            msg_list.append(ChatMessage(role="user", content=turn.user_utterance))
            msg_list.append(ChatMessage(role="assistant", content=turn.manager_response))
        msg_list.append(ChatMessage(role="user", content=utterance))
        return msg_list


__all__ = ["MANAGER_SYSTEM_PROMPT", "ManagerPersona", "ManagerTurn"]
