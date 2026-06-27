"""Registry + auto-discovery of agents — the system's extension point.

Drop a new module under ``agentic_kris/agents/`` that builds a ``BaseAgent``
subclass and calls ``register(...)`` at import time; :func:`discover` will pick
it up automatically. The orchestrator depends only on this registry, never on
concrete agent classes, so new agents require no changes elsewhere.
"""
from __future__ import annotations

import importlib
import pkgutil
from typing import Dict, List

from .base import BaseAgent


class AgentRegistry:
    def __init__(self) -> None:
        self._agents: Dict[str, BaseAgent] = {}

    def register(self, agent: BaseAgent) -> BaseAgent:
        if not agent.name:
            raise ValueError("Agent must define a non-empty 'name'.")
        self._agents[agent.name] = agent
        return agent

    def get(self, name: str) -> BaseAgent:
        if name not in self._agents:
            raise KeyError(f"Unknown agent: {name!r}. Available: {list(self._agents)}")
        return self._agents[name]

    def has(self, name: str) -> bool:
        return name in self._agents

    def all(self) -> List[BaseAgent]:
        return list(self._agents.values())

    def catalog(self) -> List[Dict[str, str]]:
        """Level-1 metadata (name + description) for every registered agent."""
        return [{"name": a.name, "description": a.description} for a in self._agents.values()]


# Global registry used across the app.
registry = AgentRegistry()


def register(agent: BaseAgent) -> BaseAgent:
    """Module-level convenience wrapper around the global registry."""
    return registry.register(agent)


def discover() -> AgentRegistry:
    """Import every sibling agent module so it self-registers; return the registry."""
    package = importlib.import_module(__package__)
    for mod in pkgutil.iter_modules(package.__path__):
        if mod.name in ("base", "registry"):
            continue
        importlib.import_module(f"{__package__}.{mod.name}")
    return registry
