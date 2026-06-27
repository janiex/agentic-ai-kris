"""Provider-agnostic LLM interface.

Every backend (local Ollama, external Anthropic Claude API, ...) implements
``stream``. ``complete`` is derived from it, so callers get both streaming and
blocking use for free. This abstraction is what lets the user pick a local LLM
or an external one at runtime without any agent code changing.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, Iterator, List

# A chat message: {"role": "user" | "assistant", "content": "..."}.
Message = Dict[str, str]


class LLMProvider(ABC):
    """Abstract base every concrete LLM backend implements."""

    name: str = "base"

    @abstractmethod
    def stream(self, system: str, messages: List[Message]) -> Iterator[str]:
        """Yield response text incrementally for the given system + messages."""
        raise NotImplementedError

    def complete(self, system: str, messages: List[Message]) -> str:
        """Blocking variant — collect the full streamed response into a string."""
        return "".join(self.stream(system, messages))

    def health_check(self) -> str:
        """Return a human-readable status string; raise on failure.

        Subclasses should make a cheap real call so the UI can verify the
        backend is reachable and configured.
        """
        return "ok"
