"""External LLM backend via the Anthropic Claude API.

Uses the official ``anthropic`` SDK. The API key is supplied explicitly (e.g.
from chat settings) or falls back to ANTHROPIC_API_KEY in the environment.
"""
from __future__ import annotations

from typing import Iterator, List

from .base import LLMProvider, Message

# Sensible default cap; long enough for documented solutions, bounded for cost.
_MAX_TOKENS = 4096


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self, api_key: str, model: str, max_tokens: int = _MAX_TOKENS):
        if not api_key:
            raise ValueError(
                "Anthropic API key is missing. Set ANTHROPIC_API_KEY in .env or "
                "enter it in the chat settings."
            )
        # Imported lazily so the package imports without the SDK installed.
        from anthropic import Anthropic

        self._client = Anthropic(api_key=api_key)
        self.model = model
        self.max_tokens = max_tokens

    def stream(self, system: str, messages: List[Message]) -> Iterator[str]:
        with self._client.messages.stream(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            messages=messages,
        ) as stream:
            yield from stream.text_stream

    def health_check(self) -> str:
        # A 1-token call confirms key + model + connectivity cheaply.
        self._client.messages.create(
            model=self.model,
            max_tokens=1,
            messages=[{"role": "user", "content": "ping"}],
        )
        return f"anthropic reachable; model '{self.model}' ok"
