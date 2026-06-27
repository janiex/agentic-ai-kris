# agentic-ai-kris 🤖

An **extensible multi-agent system**: a supervisor orchestrates specialist agents
that collaborate on a user's topic, each enhanced by **Anthropic-format Skills**,
with a **RAG-ready retrieval seam** and a **Chainlit** chat UI.

The shipped default workflow:

1. 🔬 **Researcher** studies the assigned topic and proposes a solution, grounding
   it in retrieved knowledge (RAG).
2. 🧐 **Critic** reviews the proposal and votes `APPROVE` / `REVISE`.
3. 🔁 Researcher ↔ Critic **loop, capped at 3 rounds** (stops early on `APPROVE`).
4. 📝 **Summarizer** observes the whole discussion and **documents** the
   consolidated solution as the final answer.

The system is **open by design** — adding an agent is dropping one module; adding
a skill is dropping one folder. The supervisor depends on a registry, not on
concrete agent classes.

---

## Architecture

```
        ┌──────────────── Chainlit UI (app.py) ────────────────┐
        │  chat input · live per-agent steps · settings         │
        └───────────────────────────┬───────────────────────────┘
                        ┌────────────▼────────────┐
                        │   Supervisor             │
                        │  Researcher⇄Critic (≤3)  │
                        │     → Summarizer docs     │
                        └───┬───────────────────┬───┘
              AgentRegistry │                   │ shared deps
        ┌─────────────┬─────▼─────┬─────────────┘
        │ Researcher  │  Critic   │  Summarizer        ← src/agentic_kris/agents
        └──────┬──────┴─────┬─────┴──────┬──────┐
               │ uses skills (SkillLoader)│      │
        ┌──────▼──────────────────────────▼──────▼──┐
        │ LLMProvider (ollama|anthropic) · Retriever │ ← llm / rag
        │                         (in-memory → pgvector)
        └────────────────────────────────────────────┘
```

| Concern | Where |
| --- | --- |
| Config (env-driven, cross-platform paths) | `src/agentic_kris/config.py` |
| LLM providers (local + external) | `src/agentic_kris/llm/` |
| Skills (Anthropic `SKILL.md` format) | loader in `src/agentic_kris/skills/`, packages in `skills/` |
| Agents + registry/discovery | `src/agentic_kris/agents/` |
| Orchestration (supervisor + loop policy) | `src/agentic_kris/orchestration/` |
| RAG seam (stub now, pgvector later) | `src/agentic_kris/rag/` |
| Chat UI | `app.py`, `chainlit.md` |

---

## Setup

**Python 3.10–3.13** (the Chainlit/ASGI stack does not yet support 3.14).

```bash
# 1. create a virtualenv
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\Activate.ps1

# 2. install
pip install -e ".[dev]"

# 3. configure
cp .env.example .env                 # Windows: copy .env.example .env
#   then set ANTHROPIC_API_KEY (for Claude) or run Ollama locally
```

> Using [`uv`](https://docs.astral.sh/uv/)? `uv venv --python 3.12 .venv && uv pip install -e ".[dev]"`.

### Pick an LLM backend
- **Anthropic (default):** set `ANTHROPIC_API_KEY` in `.env`, or paste a key in the
  in-app ⚙️ settings (session-only). Default model `claude-opus-4-8`.
- **Local (Ollama):** install [Ollama](https://ollama.com), `ollama pull llama3.1`,
  then choose `ollama` in ⚙️ settings. Embeddings/RAG stub run locally, so this
  path is fully offline.

---

## Run

```bash
python run.py                # → http://localhost:8000   (any OS)
PORT=8600 python run.py      # custom port
./run.sh                     # Unix convenience wrapper (activates .venv)
```

Then open the URL, type a topic (e.g. *"Design a caching layer for a read-heavy
API"*), and watch the Researcher → Critic loop and the Summarizer's final
document stream in.

---

## Skills (Anthropic format)

Each skill is a folder under `skills/` containing a `SKILL.md` with YAML
frontmatter and Markdown instructions. The loader applies **progressive
disclosure**:

- **Level 1 — metadata:** `name` + `description` (always cheap, used for selection).
- **Level 2 — instructions:** the `SKILL.md` body, injected into an agent's prompt
  only when that agent uses the skill.
- **Level 3 — resources/scripts:** bundled `reference.md`, templates, and
  `scripts/` executables, loaded/run only on demand
  (`SkillLoader.run_script(...)`).

Authoring rules (enforced by the loader, per the guide): the folder name must
equal the lowercase-hyphenated `name` (≤64 chars); `description` is third-person
and states *what it does and when to use it*; keep `SKILL.md` focused and push
depth into `reference.md`. Shipped examples: `web-research`, `critique`,
`document-solution`.

### Add a skill
1. `mkdir skills/my-skill`
2. Write `skills/my-skill/SKILL.md` with `name: my-skill` + a `description`.
3. (Optional) add `reference.md` and `scripts/`.
4. Reference it from an agent's `skill_names`. Done — the loader picks it up.

---

## Add an agent (the extension point)

Create `src/agentic_kris/agents/my_agent.py`:

```python
from .base import BaseAgent
from .registry import register

class MyAgent(BaseAgent):
    name = "my-agent"
    role = "My Agent"
    description = "What it does and when the orchestrator should use it."
    skill_names = ["my-skill"]          # optional
    system_prompt = "You are ..."

    def build_user_prompt(self, *, task, transcript, context, user_note):
        return f"{task}\n\n{transcript}"

    # optional: opt into RAG retrieval
    # def retrieval_query(self, *, task, transcript): return task

register(MyAgent())
```

`AgentRegistry.discover()` auto-imports it; the supervisor sees it via the
registry with **no other code changes**. (To weave it into the workflow, extend
`src/agentic_kris/orchestration/supervisor.py` or add a new workflow.)

---

## RAG (current state and roadmap)

Agents retrieve through the stable `Retriever` interface
(`src/agentic_kris/rag/retriever.py`). Today an **in-memory keyword stub**
(`memory_store.py`) backs it so the wiring works end-to-end and the Researcher's
retrieval is visible in the UI.

**Planned real backend** (`pgvector_store.py`, currently an inert skeleton): a
Postgres + pgvector **hybrid retriever** — dense vector kNN + sparse full-text,
fused with Reciprocal Rank Fusion, optional cross-encoder reranking. Bring up the
store with `docker compose up -d`, install the `rag` extra
(`pip install -e ".[rag]"`), implement `PgVectorRetriever`, and set
`RAG_ENABLED=true`. No agent code changes are required to switch backends.

---

## Tests

```bash
pytest          # skill loading/validation, registry discovery, provider factory,
                # verdict parsing, and a full supervisor loop (fake provider)
```

---

## Configuration

All knobs live in `.env` (see `.env.example`): LLM provider/model/key,
`MAX_REVIEW_ROUNDS`, `SKILLS_DIR`, `RAG_ENABLED`, `RETRIEVAL_TOP_K`, and the
Postgres block reserved for the future RAG backend.
