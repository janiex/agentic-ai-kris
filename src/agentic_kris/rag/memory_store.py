"""An in-memory retriever stub.

Exercises the full agent<->RAG wiring today without any external service. It does
naive keyword-overlap scoring — good enough to demonstrate retrieval and to let
the Researcher agent show retrieved context in the UI. Replaced later by
:mod:`agentic_kris.rag.pgvector_store` when the real backend lands.
"""
from __future__ import annotations

import re
from typing import Dict, List

from .retriever import RetrievedDoc

_WORD = re.compile(r"\w+")


def _tokens(text: str) -> set[str]:
    return {w.lower() for w in _WORD.findall(text)}


class InMemoryRetriever:
    """A trivial keyword-overlap retriever satisfying the Retriever protocol."""

    def __init__(self, seed_docs: List[Dict[str, object]] | None = None):
        # Each doc: {"content": str, "metadata": {...}}
        self._docs: List[Dict[str, object]] = []
        for d in seed_docs or _DEFAULT_SEED:
            self.ingest(str(d["content"]), d.get("metadata"))  # type: ignore[arg-type]

    def ingest(self, text: str, metadata: Dict[str, object] | None = None) -> int:
        text = text.strip()
        if not text:
            return 0
        self._docs.append({"content": text, "metadata": metadata or {}})
        return 1

    def retrieve(self, query: str, top_k: int = 5) -> List[RetrievedDoc]:
        q = _tokens(query)
        if not q:
            return []
        scored: List[RetrievedDoc] = []
        for d in self._docs:
            content = str(d["content"])
            overlap = q & _tokens(content)
            if not overlap:
                continue
            score = len(overlap) / len(q)
            scored.append(
                RetrievedDoc(content=content, score=score, metadata=dict(d["metadata"]))  # type: ignore[arg-type]
            )
        scored.sort(key=lambda r: r.score, reverse=True)
        return scored[:top_k]


# A couple of seed passages so the demo shows retrieval working out of the box.
_DEFAULT_SEED: List[Dict[str, object]] = [
    {
        "content": (
            "Retrieval-Augmented Generation (RAG) grounds an LLM's answers in "
            "retrieved passages. A hybrid retriever fuses dense vector (semantic) "
            "search with sparse keyword (BM25) search, commonly combined via "
            "Reciprocal Rank Fusion."
        ),
        "metadata": {"source": "seed: rag-overview"},
    },
    {
        "content": (
            "A supervisor/orchestrator pattern routes a user request to specialist "
            "agents and composes their outputs. It keeps the system open to adding "
            "new agents without rewiring existing ones."
        ),
        "metadata": {"source": "seed: orchestration"},
    },
]
