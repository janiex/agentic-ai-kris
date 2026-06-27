"""RAG retrieval seam: a stable interface now, a real backend later.

``get_retriever`` returns the in-memory stub unless RAG is enabled and the
pgvector backend has been implemented.
"""
from __future__ import annotations

from ..config import settings
from .memory_store import InMemoryRetriever
from .retriever import RetrievedDoc, Retriever, format_context

__all__ = [
    "Retriever",
    "RetrievedDoc",
    "format_context",
    "InMemoryRetriever",
    "get_retriever",
]


def get_retriever(rag_enabled: bool | None = None) -> Retriever:
    """Build the active retriever.

    Defaults to the in-memory stub. When RAG is enabled, attempt the real
    pgvector backend (which currently raises until implemented), so the seam is
    explicit and the fallback is intentional rather than silent.
    """
    enabled = settings.rag_enabled if rag_enabled is None else rag_enabled
    if enabled:
        from .pgvector_store import PgVectorRetriever

        return PgVectorRetriever(settings.pg_dsn)
    return InMemoryRetriever()
