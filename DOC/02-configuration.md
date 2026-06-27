# 2. Configuration

**File:** `src/agentic_kris/config.py`

Every tunable lives in a single `Settings` object built from environment
variables / a project-root `.env` file. The module is deliberately
**import-light** (only `pydantic-settings`) so it can be imported from the CLI
launcher, the Chainlit app, and the tests without dragging in heavy dependencies.

## 2.1 The `Settings` class

`Settings` is a `pydantic_settings.BaseSettings` subclass. Field names map to env
vars case-insensitively, so the field `anthropic_api_key` is populated from
`ANTHROPIC_API_KEY`.

Groups of settings:

| Group | Fields | Notes |
| --- | --- | --- |
| LLM | `llm_provider`, `ollama_host`, `ollama_model`, `anthropic_api_key`, `anthropic_model` | Default provider `anthropic`, model `claude-opus-4-8` |
| Orchestration | `max_review_rounds` (default 3, bounded 1–10) | Caps the Researcher↔Critic loop |
| Skills | `skills_dir` (default `skills`) | Where skill packages live |
| RAG | `rag_enabled` (default `false`), `retrieval_top_k` | Gates the real backend |
| Postgres | `pghost`, `pgport`, `pguser`, `pgpassword`, `pgdatabase` | Reserved for the future pgvector backend |

## 2.2 Cross-platform paths

`PROJECT_ROOT` is derived from the file location, not the current working
directory, so the app works regardless of where it's launched from:

```python
PROJECT_ROOT = Path(__file__).resolve().parents[2]   # .../agentic-ai-kris
```

Two derived helpers:

- `settings.skills_path` → an **absolute** `Path` to the skills directory. A
  relative `SKILLS_DIR` resolves against `PROJECT_ROOT`; an absolute one is used
  as-is.
- `settings.pg_dsn` → a libpq DSN string assembled from the Postgres fields (used
  later by the pgvector backend).

## 2.3 The singleton

```python
@lru_cache
def get_settings() -> Settings: ...
settings = get_settings()
```

`settings` is the shared instance everything imports. `get_settings` is cached so
repeated imports are free. In tests you can clear the cache to force a re-read
after changing the environment (see the experiment below).

## 2.4 Where settings are consumed

- `llm/factory.py` reads `llm_provider`, `ollama_*`, `anthropic_*`.
- `app.py` reads `skills_path`, `max_review_rounds`, `retrieval_top_k`,
  `llm_provider`.
- `rag/__init__.py` reads `rag_enabled` and `pg_dsn`.

### 🧪 Experiment — inspect the live settings

```bash
python -c "
from agentic_kris.config import settings
print('provider     :', settings.llm_provider)
print('anthropic mdl:', settings.anthropic_model)
print('review rounds:', settings.max_review_rounds)
print('skills path  :', settings.skills_path)
print('skills exist :', settings.skills_path.is_dir())
print('pg dsn       :', settings.pg_dsn)
"
```

### 🧪 Experiment — override via environment, with cache reset

`Settings` reads the environment at construction, so override *before* the object
is built (or clear the cache):

```bash
MAX_REVIEW_ROUNDS=5 LLM_PROVIDER=ollama python -c "
from agentic_kris.config import get_settings
get_settings.cache_clear()          # drop the cached singleton
s = get_settings()
print(s.llm_provider, s.max_review_rounds)   # -> ollama 5
"
```

> The bound on `max_review_rounds` (1–10) is enforced by pydantic: setting
> `MAX_REVIEW_ROUNDS=99` raises a validation error at startup — a deliberate
> guard so a typo can't launch a 99-round loop.
