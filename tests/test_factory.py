"""LLM provider factory."""
from __future__ import annotations

import pytest

from agentic_kris.llm.factory import available_providers, get_provider


def test_available_providers():
    assert set(available_providers()) == {"anthropic", "ollama"}


def test_unknown_provider_raises():
    with pytest.raises(ValueError):
        get_provider("nope")


def test_ollama_provider_builds_without_network():
    p = get_provider("ollama", model="llama3.1")
    assert p.name == "ollama"
    assert p.model == "llama3.1"


def test_anthropic_requires_key():
    with pytest.raises(ValueError):
        get_provider("anthropic", api_key="")
