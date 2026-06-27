"""Agent registration and auto-discovery (the extension point)."""
from __future__ import annotations

from agentic_kris.agents.base import BaseAgent
from agentic_kris.agents.registry import AgentRegistry


def test_discovery_registers_core_agents(registry):
    names = {a.name for a in registry.all()}
    assert {"researcher", "critic", "summarizer"} <= names


def test_catalog_is_metadata(registry):
    for entry in registry.catalog():
        assert set(entry) == {"name", "description"}


def test_a_new_agent_can_be_registered():
    reg = AgentRegistry()

    class Dummy(BaseAgent):
        name = "dummy"
        description = "d"
        role = "Dummy"

        def build_user_prompt(self, *, task, transcript, context, user_note):
            return task

    reg.register(Dummy())
    assert reg.has("dummy")
    assert reg.get("dummy").role == "Dummy"
