# 11. Extending the system

The system is built to grow by **addition, not modification**. This chapter shows
the four common extensions and exactly which files they touch.

## 11.1 Add a skill (zero code)

1. Create the folder and `SKILL.md`:

   ```bash
   mkdir -p skills/threat-model
   cat > skills/threat-model/SKILL.md <<'EOF'
   ---
   name: threat-model
   description: >-
     Enumerates assets, threats, and mitigations for a proposed design. Use when
     a solution needs a security pass before it is finalized.
   ---
   # Threat modelling
   For the proposed design, list: assets, trust boundaries, likely threats
   (STRIDE), and a concrete mitigation per threat.
   EOF
   ```

2. (Optional) add `reference.md` and `scripts/`.
3. Reference it from any agent's `skill_names` (or a new agent).

The loader validates it on next start; `prompt_for([...])` injects its body. No
code changes. See [04-skills.md](04-skills.md) for the authoring rules the loader
enforces.

## 11.2 Add an agent (one file)

Create `src/agentic_kris/agents/security_reviewer.py`:

```python
from .base import BaseAgent
from .registry import register

class SecurityReviewer(BaseAgent):
    name = "security-reviewer"
    role = "Security Reviewer"
    description = "Reviews a proposed design for security risks using threat modelling."
    skill_names = ["threat-model"]
    system_prompt = "You are a security reviewer. Be specific about risks and fixes."

    def build_user_prompt(self, *, task, transcript, context, user_note):
        return f"TASK:\n{task}\n\nDISCUSSION:\n{transcript}\n\nReview for security risks."

    # Opt into RAG if useful:
    # def retrieval_query(self, *, task, transcript):
    #     return task

register(SecurityReviewer())
```

`AgentRegistry.discover()` auto-imports it. It's now retrievable via
`registry.get("security-reviewer")` and appears in `registry.catalog()`. **No
edits to the registry, supervisor, or UI** are required for it to exist.

To make the supervisor actually *call* it in the workflow, see §11.4.

## 11.3 Add an LLM provider

1. Implement the interface in `src/agentic_kris/llm/your_provider.py`:

   ```python
   from .base import LLMProvider, Message
   from typing import Iterator, List

   class YourProvider(LLMProvider):
       name = "yours"
       def __init__(self, ...): ...
       def stream(self, system: str, messages: List[Message]) -> Iterator[str]:
           ...  # yield text chunks
       def health_check(self) -> str:
           ...  # cheap probe; raise on failure
   ```

2. Wire it into `factory.py`: add `"yours"` to `AVAILABLE` and a branch in
   `get_provider`.

`complete()` comes for free from `stream()`. The UI's provider `Select` picks it
up automatically from `available_providers()`.

## 11.4 Add or change a workflow

The default workflow lives in `Supervisor.run` (`orchestration/supervisor.py`) and
its loop policy in `workflow.py`. Two paths:

- **Tweak the existing loop** — e.g. change the cap, or add a third agent into the
  loop: edit `run` to call your agent via `_run_turn` and append its turn to the
  transcript. Reuse `_run_turn` so streaming + retrieval events keep working.
- **Add a parallel workflow** — create a new orchestrator class (or a new
  `run_*` method) that composes agents differently (sequential pipeline, parallel
  fan-out, conditional routing). Keep it yielding `Event`s so the existing UI and
  test patterns apply unchanged.

Example — insert the new Security Reviewer after the Critic each round:

```python
# inside Supervisor.run, after the Critic turn and before should_continue():
reviewer = self.registry.get("security-reviewer")
content = ""
for ev in self._run_turn(reviewer, task=task, transcript=transcript,
                         round=state.round, user_note=user_note):
    if ev.kind == "turn_end":
        content = ev.content
    yield ev
transcript.append(Turn(reviewer.role, state.round, content))
```

Because `_run_turn` already handles streaming, retrieval, and event emission, the
UI renders the new agent's step with no UI changes.

## 11.5 Implement the real RAG backend

1. `pip install -e ".[rag]"` (sentence-transformers, psycopg2-binary, pgvector).
2. `docker compose up -d` to bring up Postgres + pgvector.
3. Implement `PgVectorRetriever.retrieve` / `ingest` in
   `src/agentic_kris/rag/pgvector_store.py` per the design in its docstring
   (dense kNN + sparse full-text, RRF fusion, optional reranking).
4. Set `RAG_ENABLED=true` and point the UI's `_build_supervisor` at
   `get_retriever(use_rag)` instead of the hard-coded stub.

Agents need **no changes** — they already call the `Retriever` interface. See
[07-rag.md](07-rag.md).

## 11.6 Extension checklist

After any extension, confirm nothing regressed:

```bash
pytest -q                 # existing behaviour intact
python -c "import app"    # UI wiring still imports
```

And, for a new agent/skill, the discovery smoke test:

```bash
python -c "
from agentic_kris.agents.registry import discover
from agentic_kris.skills.loader import SkillLoader
from agentic_kris.config import settings
print('agents:', sorted(a.name for a in discover().all()))
print('skills:', sorted(SkillLoader(settings.skills_path).names()))
"
```
