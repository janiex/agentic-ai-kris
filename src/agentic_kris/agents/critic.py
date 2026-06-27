"""Critic — reviews the Researcher's latest proposal and issues a verdict.

The verdict line (``VERDICT: APPROVE | REVISE``) is what the supervisor parses to
decide whether the research<->critique loop continues.
"""
from __future__ import annotations

from .base import BaseAgent
from .registry import register

_SYSTEM = """You are the Critic, a rigorous reviewer.
Challenge the Researcher's most recent proposal: hunt for incorrect assumptions,
missing cases, risks (security, scalability, cost, correctness), and simpler
alternatives. Be specific and constructive — explain why each issue matters and
what would fix it. Acknowledge what is genuinely good. Do not manufacture
objections. End with exactly one verdict line."""


class CriticAgent(BaseAgent):
    name = "critic"
    role = "Critic"
    description = (
        "Critically reviews the Researcher's proposal for correctness, gaps, and "
        "risk, then issues VERDICT: APPROVE or VERDICT: REVISE to drive the loop."
    )
    skill_names = ["critique"]
    system_prompt = _SYSTEM

    def build_user_prompt(
        self, *, task: str, transcript: str, context: str, user_note: str
    ) -> str:
        parts = [
            f"ASSIGNED TOPIC:\n{task}\n",
            f"DISCUSSION SO FAR:\n{transcript}\n",
            "Critically review the Researcher's most recent proposal. "
            "End with your single VERDICT line (APPROVE or REVISE).",
        ]
        if user_note:
            parts.append(f"\nUSER GUIDANCE (treat as a priority):\n{user_note}")
        return "\n".join(parts)


register(CriticAgent())
