# 7. RAG — the retrieval seam

**Package:** `src/agentic_kris/rag/`

RAG is a **future integration**, but the *interface* exists today so agents can
already retrieve, and the real backend can be dropped in later without touching
agent code.

## 7.1 The contract — `retriever.py`

```python
@dataclass
class RetrievedDoc:
    content: str
    score: float = 0.0
    metadata: dict = {}

@runtime_checkable
class Retriever(Protocol):
    def retrieve(self, query: str, top_k: int = 5) -> list[RetrievedDoc]: ...
    def ingest(self, text: str, metadata: dict | None = None) -> int: ...

def format_context(docs) -> str:    # renders docs as labelled [K1], [K2] blocks
```

- `Retriever` is a **`Protocol`** (structural typing): any object with matching
  `retrieve`/`ingest` methods *is* a retriever — no inheritance required. This is
  what lets the in-memory stub and the future pgvector class be interchangeable.
- `format_context` produces the `[K1] (source)\n<content>` blocks the Researcher
  cites in its prompt. The `[K1]` labels are how citations stay traceable.

## 7.2 The stub backend — `memory_store.py`

`InMemoryRetriever` satisfies the protocol with naive keyword-overlap scoring:

- `retrieve(query, top_k)` tokenises the query and each stored doc, scores by the
  fraction of query words present, sorts, and returns the top `k`.
- `ingest(text, metadata)` appends a doc.
- It seeds two passages (`_DEFAULT_SEED`) about RAG and orchestration so the demo
  shows retrieval working out of the box.

It exists so the **whole agent↔RAG path runs end-to-end today** — the Researcher
retrieves, the UI shows a `retrieved` event — without any external service.

## 7.3 The planned backend — `pgvector_store.py`

`PgVectorRetriever` is an **inert skeleton**: constructing it raises
`NotImplementedError` with guidance. Its docstring specifies the intended design:

- **dense channel** — pgvector cosine kNN over local sentence-transformer
  embeddings (e.g. `all-mpnet-base-v2`, 768-dim), HNSW index;
- **sparse channel** — Postgres full-text search (`tsvector` + `ts_rank_cd`),
  BM25-style;
- **fusion** — Reciprocal Rank Fusion of the two ranked lists;
- **optional** — cross-encoder reranking of the fused candidates.

Provisioning is ready: `docker-compose.yml` brings up `pgvector/pgvector:pg16`;
the `rag` optional dependency group (`pip install -e ".[rag]"`) pulls
`sentence-transformers`, `psycopg2-binary`, and `pgvector`.

## 7.4 Selecting a backend — `__init__.py`

```python
def get_retriever(rag_enabled: bool | None = None) -> Retriever:
    enabled = settings.rag_enabled if rag_enabled is None else rag_enabled
    if enabled:
        return PgVectorRetriever(settings.pg_dsn)   # raises until implemented
    return InMemoryRetriever()
```

The intent: enabling RAG is an explicit, *visible* switch to the real backend
(which currently raises by design), rather than a silent fallback.

> **UI note:** `app.py` does **not** call `get_retriever`. To keep the current
> demo runnable while pgvector is unimplemented, the UI uses the in-memory stub
> when the "Use RAG" switch is on and `None` (no retrieval) when off — see
> `_build_supervisor` in `app.py`. Once `PgVectorRetriever` is implemented, point
> the UI at `get_retriever(use_rag)` to flip onto the real store.

## 7.5 How retrieval reaches an agent

1. `Supervisor` is constructed with a `retriever`.
2. It passes that retriever into `agent.stream(...)`.
3. `BaseAgent.stream` calls `self.retrieval_query(...)`; the Researcher returns
   the task, so retrieval runs; other agents return `None` and skip it.
4. Retrieved docs are formatted by `format_context` and spliced into the
   Researcher's user prompt as `[K1]…`; an `on_retrieve` callback lets the
   supervisor emit a `retrieved` event.

### 🧪 Experiment — query the stub directly

```bash
python -c "
from agentic_kris.rag.memory_store import InMemoryRetriever
from agentic_kris.rag.retriever import format_context
r = InMemoryRetriever()
docs = r.retrieve('how does hybrid retrieval fuse dense and sparse search?', top_k=3)
for d in docs:
    print(round(d.score,2), d.metadata.get('source'), '::', d.content[:60], '...')
print('--- formatted for the prompt ---')
print(format_context(docs))
"
```

### 🧪 Experiment — ingest your own knowledge, then retrieve it

```bash
python -c "
from agentic_kris.rag.memory_store import InMemoryRetriever
r = InMemoryRetriever()
r.ingest('Chainlit renders agent steps as collapsible UI elements.',
         metadata={'source':'my-note'})
docs = r.retrieve('how are chainlit steps rendered?', top_k=2)
print([d.metadata.get('source') for d in docs])     # includes 'my-note'
"
```

### 🧪 Experiment — prove the seam: a custom retriever in 5 lines

Any object matching the protocol works as a drop-in backend:

```bash
python -c "
from agentic_kris.rag.retriever import Retriever, RetrievedDoc
class ConstRetriever:
    def retrieve(self, query, top_k=5):
        return [RetrievedDoc(content='always this', score=1.0, metadata={'source':'const'})]
    def ingest(self, text, metadata=None): return 0
print('is a Retriever:', isinstance(ConstRetriever(), Retriever))   # True (structural)
"
```

### 🧪 Experiment — see that enabling RAG selects the (unimplemented) real backend

```bash
python -c "
from agentic_kris.rag import get_retriever
print(type(get_retriever(False)).__name__)      # InMemoryRetriever
try:
    get_retriever(True)
except NotImplementedError as e:
    print('pgvector not built yet:', str(e)[:60], '...')
"
```
