"""Researcher — studies the user-assigned topic and proposes a solution.

Opts into RAG retrieval (the only agent that does by default) and uses the
``web-research`` skill. On later rounds it revises its proposal to address the
Critic's points.
"""
from __future__ import annotations

from typing import Optional

from .base import BaseAgent
from .registry import register

_SYSTEM = """You are the Researcher, a thorough solution architect.
Your job is to study the user's assigned topic and PROPOSE a concrete, grounded
solution. Prefer specifics — steps, components, trade-offs — over vague advice.
Ground claims in the retrieved knowledge when it is relevant and cite it. When
the Critic raises points, address each one directly in your revision."""


class ResearcherAgent(BaseAgent):
    name = "researcher"
    role = "Researcher"
    description = (
        "Investigates the assigned topic, gathers and synthesizes information "
        "(including from RAG), and proposes a concrete, cited solution; revises "
        "it to address the Critic's feedback."
    )
    skill_names = ["web-research"]
    system_prompt = _SYSTEM

    def retrieval_query(self, *, task: str, transcript: str) -> Optional[str]:
        # Researcher always tries to ground its work in retrieved knowledge.
        return task

    def build_user_prompt(
        self, *, task: str, transcript: str, context: str, user_note: str
    ) -> str:
        parts = []
        if context:
            parts.append(f"RETRIEVED KNOWLEDGE (cite as [K1], [K2], …):\n{context}\n")
        else:
            parts.append("RETRIEVED KNOWLEDGE: (none found — reason from first principles)\n")
        parts.append(f"ASSIGNED TOPIC:\n{task}\n")
        if transcript:
            parts.append(f"DISCUSSION SO FAR:\n{transcript}\n")
            parts.append("Provide your REVISED proposal, addressing the Critic's latest points.")
        else:
            parts.append("Provide your initial proposed solution.")
        if user_note:
            parts.append(f"\nUSER GUIDANCE (treat as a priority):\n{user_note}")
        return "\n".join(parts)


register(ResearcherAgent())
