"""The retrieval seam agents use to pull knowledge from a RAG layer.

RAG is a *future* integration. This module defines the stable contract now —
:class:`Retriever` and :class:`RetrievedDoc` — so agents can call it today
against an in-memory stub and be swapped onto a real Postgres+pgvector backend
later without any agent changes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Protocol, runtime_checkable


@dataclass
class RetrievedDoc:
    content: str
    score: float = 0.0
    metadata: Dict[str, object] = field(default_factory=dict)


@runtime_checkable
class Retriever(Protocol):
    """What every retrieval backend must provide."""

    def retrieve(self, query: str, top_k: int = 5) -> List[RetrievedDoc]:
        """Return up to ``top_k`` passages relevant to ``query``."""
        ...

    def ingest(self, text: str, metadata: Dict[str, object] | None = None) -> int:
        """Add ``text`` to the store; return the number of chunks indexed."""
        ...


def format_context(docs: List[RetrievedDoc]) -> str:
    """Render retrieved passages as a labelled block for an agent prompt."""
    if not docs:
        return ""
    blocks = []
    for i, d in enumerate(docs, 1):
        src = d.metadata.get("source") or d.metadata.get("title") or ""
        head = f"[K{i}]" + (f" ({src})" if src else "")
        blocks.append(f"{head}\n{d.content}")
    return "\n\n".join(blocks)
