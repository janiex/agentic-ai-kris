# 10. Testing and experiments

The core is designed to be testable **without a browser, an API key, or a
database** — the UI-agnostic event stream and the interface-based design make
fake doubles trivial.

## 10.1 The test suite

**Location:** `tests/` · **Runner:** `pytest` (configured in `pyproject.toml`
with `pythonpath=["src"]` and `testpaths=["tests"]`).

| File | Validates |
| --- | --- |
| `tests/conftest.py` | shared fixtures: `FakeProvider`, `loader`, `registry` |
| `tests/test_skills.py` | skill loading, the 3 disclosure levels, frontmatter validation, the bundled script |
| `tests/test_registry.py` | agent discovery and registration (the extension point) |
| `tests/test_factory.py` | provider selection, fail-fast on a missing key, no-network construction |
| `tests/test_workflow.py` | `parse_verdict` cases and `LoopState` policy |
| `tests/test_supervisor.py` | the full loop: early stop on `APPROVE`, the round cap, retrieval surfacing, token streaming |

Run everything:

```bash
pytest -q
```

Run one area, verbosely:

```bash
pytest tests/test_supervisor.py -v
pytest -k verdict -v
```

## 10.2 The key test double — `FakeProvider`

In `tests/conftest.py`, `FakeProvider` is an `LLMProvider` that responds based on
which agent's system prompt it sees, with a **configurable Critic verdict
sequence**:

```python
FakeProvider(["REVISE", "APPROVE"])   # revise once, then approve -> 2 rounds
FakeProvider(["APPROVE"])             # approve immediately       -> 1 round
```

This is the single most useful tool for experimenting with orchestration: you
script the verdicts and assert on the resulting event stream. Because it keys off
substrings in the system prompt (`"Critic"`, `"Researcher"`, `"Summarizer"`), it
naturally routes the right canned response to the right agent.

## 10.3 How `test_supervisor.py` reads the event stream

The supervisor yields a flat list of `Event`s, so assertions are simple:

```python
events = list(sup.run("How does RAG work?"))
rounds = max(e.round for e in events if e.kind == "turn_end")
assert any(e.kind == "final" and e.content for e in events)
assert any(e.kind == "retrieved" and e.role == "Researcher" for e in events)
```

That pattern — *run, collect events, assert on kinds/roles/rounds* — is how you
test any new workflow you add.

## 10.4 Writing your own experiment

A self-contained template you can copy into a scratch file
(`scratch_experiment.py` at the project root) and run with `python`:

```python
from agentic_kris.orchestration.supervisor import Supervisor
from agentic_kris.agents.registry import discover
from agentic_kris.skills.loader import SkillLoader
from agentic_kris.config import settings
from agentic_kris.rag.memory_store import InMemoryRetriever
from agentic_kris.llm.base import LLMProvider


class ScriptedProvider(LLMProvider):
    """Return canned text per agent so you can probe orchestration offline."""
    name = "scripted"

    def __init__(self, verdicts):
        self.verdicts, self.i = verdicts, 0

    def stream(self, system, messages):
        # Match the unique opener; the Researcher prompt also mentions 'Critic'.
        if "You are the Critic" in system:
            v = self.verdicts[min(self.i, len(self.verdicts) - 1)]
            self.i += 1
            yield f"My review.\nVERDICT: {v}"
        elif "You are the Researcher" in system:
            yield "A proposal citing [K1]."
        else:
            yield "# Final\n## Recommendation\nThe documented answer."


sup = Supervisor(
    provider=ScriptedProvider(["REVISE", "REVISE", "APPROVE"]),
    loader=SkillLoader(settings.skills_path),
    registry=discover(),
    retriever=InMemoryRetriever(),
    max_rounds=5,
)

for ev in sup.run("Design a cache for a read-heavy API"):
    if ev.kind == "token":
        continue
    print(ev.kind, ev.role, ev.round, ev.verdict)
```

Change the verdict list, `max_rounds`, the retriever, or the canned text to probe
different behaviours.

## 10.5 Experiment index (per layer)

Each layer doc has runnable `🧪 Experiment` boxes. Quick links:

- **Config** — inspect/override settings: [02-configuration.md](02-configuration.md)
- **LLM** — build providers, a 4-line fake, a real Ollama call: [03-llm-providers.md](03-llm-providers.md)
- **Skills** — disclosure levels, prompt blocks, run a script, author a skill: [04-skills.md](04-skills.md)
- **Agents** — discovery, run one agent in isolation, add an agent: [05-agents-and-registry.md](05-agents-and-registry.md)
- **Orchestration** — full workflow, force the cap, verdict parsing: [06-orchestration.md](06-orchestration.md)
- **RAG** — query the stub, ingest, custom retriever, the seam: [07-rag.md](07-rag.md)
- **UI** — boot and probe the server, full chat: [08-chainlit-ui.md](08-chainlit-ui.md)

## 10.6 Pre-flight checklist

Before a real run, this confirms the whole stack is healthy without spending LLM
tokens:

```bash
pytest -q                                  # 1. logic is green
python -c "from agentic_kris.config import settings; print(settings.skills_path.is_dir())"   # 2. skills found
python -c "import app; print('UI imports OK')"   # 3. UI wiring imports
```
