"""Shared test fixtures: a fake LLM provider and loaded skills/registry."""
from __future__ import annotations

from typing import Iterator, List

import pytest

from agentic_kris.agents.registry import discover
from agentic_kris.config import settings
from agentic_kris.llm.base import LLMProvider, Message
from agentic_kris.skills.loader import SkillLoader


class FakeProvider(LLMProvider):
    """Deterministic provider that responds based on the agent's system prompt.

    The Critic's verdict sequence is configurable so tests can drive the loop
    toward early approval or the round cap.
    """

    name = "fake"

    def __init__(self, critic_verdicts: List[str] | None = None):
        # Default: approve immediately (single round).
        self._verdicts = list(critic_verdicts or ["APPROVE"])
        self._critic_calls = 0

    def stream(self, system: str, messages: List[Message]) -> Iterator[str]:
        # Key on the unique "You are the <Role>" opener — robust because the
        # Researcher's prompt also *mentions* the Critic.
        if "You are the Critic" in system:
            verdict = self._verdicts[min(self._critic_calls, len(self._verdicts) - 1)]
            self._critic_calls += 1
            yield f"Review of the proposal.\nVERDICT: {verdict}"
        elif "You are the Researcher" in system:
            yield "Proposed solution with citation [K1]."
        elif "You are the Summarizer" in system:
            yield "# Final\n## Recommendation\nThe documented solution."
        else:
            yield "ok"


@pytest.fixture
def loader() -> SkillLoader:
    return SkillLoader(settings.skills_path)


@pytest.fixture
def registry():
    return discover()
