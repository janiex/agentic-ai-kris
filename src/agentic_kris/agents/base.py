"""Base class shared by every specialist agent.

An agent is mostly *configuration* — a name, a description (used for level-1
discovery), a system prompt, and the skills it may use — plus a small amount of
prompt-shaping logic. The :meth:`BaseAgent.stream` method is generic: it
optionally retrieves RAG context, injects the agent's skill instructions, builds
the user prompt, and streams the LLM response.

Adding a new agent therefore means subclassing this and registering it — no
orchestrator or UI changes required.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable, Iterator, List, Optional

from ..llm.base import LLMProvider
from ..rag.retriever import RetrievedDoc, Retriever, format_context
from ..skills.loader import SkillLoader


class BaseAgent(ABC):
    #: stable identifier, also used in the registry
    name: str = "agent"
    #: third-person summary used for level-1 discovery / routing
    description: str = ""
    #: human-facing role label (shown in the UI)
    role: str = ""
    #: names of skills (folders under skills/) this agent may use
    skill_names: List[str] = []
    #: base system prompt; skill instructions are appended automatically
    system_prompt: str = ""

    # ── prompt assembly ──────────────────────────────────────────────────────
    def build_system(self, loader: SkillLoader) -> str:
        """System prompt + the instruction bodies of this agent's skills (level 2)."""
        block = loader.prompt_for(self.skill_names)
        if block:
            return (
                f"{self.system_prompt}\n\n"
                f"# Skills available to you\n"
                f"Apply these skill instructions when relevant:\n\n{block}"
            )
        return self.system_prompt

    @abstractmethod
    def build_user_prompt(
        self, *, task: str, transcript: str, context: str, user_note: str
    ) -> str:
        """Construct the user-turn prompt for this agent."""

    def retrieval_query(self, *, task: str, transcript: str) -> Optional[str]:
        """Return a RAG query string to opt into retrieval, or None to skip it.

        Default: no retrieval. Agents that should pull from the knowledge base
        (e.g. the Researcher) override this.
        """
        return None

    # ── execution ────────────────────────────────────────────────────────────
    def stream(
        self,
        *,
        provider: LLMProvider,
        loader: SkillLoader,
        task: str,
        transcript: str = "",
        user_note: str = "",
        retriever: Optional[Retriever] = None,
        top_k: int = 5,
        on_retrieve: Optional[Callable[[List[RetrievedDoc]], None]] = None,
    ) -> Iterator[str]:
        """Optionally retrieve context, then stream the agent's response."""
        context = ""
        query = self.retrieval_query(task=task, transcript=transcript)
        if query and retriever is not None:
            docs = retriever.retrieve(query, top_k=top_k)
            context = format_context(docs)
            if on_retrieve is not None:
                on_retrieve(docs)

        system = self.build_system(loader)
        user = self.build_user_prompt(
            task=task, transcript=transcript, context=context, user_note=user_note
        )
        yield from provider.stream(system, [{"role": "user", "content": user}])
