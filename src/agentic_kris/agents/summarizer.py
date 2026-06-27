"""Summarizer — documents the consolidated solution from the full discussion.

Runs once the research<->critique loop converges (Critic approves) or hits the
round cap. It observes the whole transcript and writes the final, self-contained
document the user receives.
"""
from __future__ import annotations

from .base import BaseAgent
from .registry import register

_SYSTEM = """You are the Summarizer/Documenter, a neutral facilitator.
The Researcher and Critic have discussed a solution. Write the FINAL,
self-contained consolidated document the user keeps. Synthesize the strongest
proposal plus the valid critiques into one coherent answer; drop rejected
dead-ends. If the discussion ended without full agreement, state the remaining
open points honestly under Caveats. Do not introduce new opinions of your own."""


class SummarizerAgent(BaseAgent):
    name = "summarizer"
    role = "Summarizer"
    description = (
        "Observes the Researcher<->Critic discussion and documents the final, "
        "self-contained consolidated solution for the user."
    )
    skill_names = ["document-solution"]
    system_prompt = _SYSTEM

    def build_user_prompt(
        self, *, task: str, transcript: str, context: str, user_note: str
    ) -> str:
        parts = [
            f"ASSIGNED TOPIC:\n{task}\n",
            f"FULL DISCUSSION (Researcher ↔ Critic):\n{transcript}\n",
            "Write the final consolidated solution document.",
        ]
        if user_note:
            parts.append(f"\nUSER GUIDANCE (treat as a priority):\n{user_note}")
        return "\n".join(parts)


register(SummarizerAgent())
