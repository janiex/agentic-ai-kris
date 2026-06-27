"""Planned Postgres + pgvector retriever — SKELETON, not yet implemented.

This file documents the intended real RAG backend so the seam is obvious. It is
deliberately inert: constructing it raises ``NotImplementedError`` unless/until
the RAG phase is built. Selection is gated by ``settings.rag_enabled`` in the
factory.

Planned design (hybrid retrieval):
  * dense channel  — pgvector cosine kNN over local sentence-transformer
                     embeddings (e.g. all-mpnet-base-v2, 768-dim), HNSW index;
  * sparse channel — Postgres full-text search (tsvector + ts_rank_cd), BM25-style;
  * fusion         — Reciprocal Rank Fusion (k≈60) of the two ranked lists;
  * optional       — cross-encoder reranking of the fused top candidates.

Provisioning: docker-compose.yml brings up Postgres+pgvector; a one-time
init_db creates the schema/indexes. Requires the optional ``rag`` extras
(sentence-transformers, psycopg2-binary, pgvector).
"""
from __future__ import annotations

from typing import Dict, List

from .retriever import RetrievedDoc


class PgVectorRetriever:
    """Hybrid dense+sparse retriever over Postgres+pgvector (to be implemented)."""

    def __init__(self, dsn: str, *, embedding_model: str = "sentence-transformers/all-mpnet-base-v2"):
        raise NotImplementedError(
            "PgVectorRetriever is a planned backend. Implement it in the RAG phase, "
            "then install the 'rag' optional dependencies. Until then run with "
            "RAG_ENABLED=false (in-memory stub)."
        )

    def retrieve(self, query: str, top_k: int = 5) -> List[RetrievedDoc]:  # pragma: no cover
        raise NotImplementedError

    def ingest(self, text: str, metadata: Dict[str, object] | None = None) -> int:  # pragma: no cover
        raise NotImplementedError
