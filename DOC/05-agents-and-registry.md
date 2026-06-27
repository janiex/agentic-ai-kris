# 5. Agents and the registry

**Package:** `src/agentic_kris/agents/`

An agent is **mostly configuration** — a name, a description, a system prompt, and
the skills it may use — over a shared `BaseAgent` that does the generic work of
retrieving context, injecting skills, building the prompt, and streaming.

## 5.1 `BaseAgent` — `base.py`

Class attributes every agent sets:

| Attribute | Purpose |
| --- | --- |
| `name` | Stable id, also the registry key |
| `description` | Third-person summary used for **level-1 discovery** |
| `role` | Human-facing label shown in the UI ("Researcher") |
| `skill_names` | Skills (folders under `skills/`) this agent may use |
| `system_prompt` | Base system prompt; skill instructions are appended automatically |

Methods:

- `build_system(loader)` — returns `system_prompt` + the level-2 instruction
  bodies of `skill_names` (via `loader.prompt_for(...)`) under a
  `# Skills available to you` header.
- `build_user_prompt(*, task, transcript, context, user_note)` — **abstract**;
  each agent shapes its own user turn.
- `retrieval_query(*, task, transcript)` — returns a RAG query string to **opt
  into** retrieval, or `None` (default) to skip it. Overriding this is how an
  agent declares "I want RAG."
- `stream(*, provider, loader, task, transcript="", user_note="",
  retriever=None, top_k=5, on_retrieve=None)` — the generic execution path:
  1. If `retrieval_query(...)` returns a query **and** a `retriever` is present,
     call `retriever.retrieve(query, top_k)`, format it with
     `rag.retriever.format_context(...)`, and fire the `on_retrieve` callback.
  2. Build the system prompt (`build_system`) and the user prompt
     (`build_user_prompt`).
  3. Delegate to `provider.stream(system, [{"role": "user", ...}])` and yield
     tokens.

Because retrieval, skill injection, and streaming all live in the base class, a
new agent only writes `build_user_prompt` (and optionally `retrieval_query`).

## 5.2 The three shipped agents

All three are tiny subclasses:

| Agent | File | `skill_names` | RAG? | Special |
| --- | --- | --- | --- | --- |
| `ResearcherAgent` | `researcher.py` | `["web-research"]` | **Yes** — `retrieval_query` returns the task | Proposes / revises the solution |
| `CriticAgent` | `critic.py` | `["critique"]` | No | Ends with `VERDICT: APPROVE|REVISE` |
| `SummarizerAgent` | `summarizer.py` | `["document-solution"]` | No | Documents the consolidated solution |

Each file ends with `register(<Agent>())`, which adds the instance to the global
registry at import time.

- The **Researcher** is the only agent overriding `retrieval_query` (returns the
  task), so it's the one that pulls from RAG. Its `build_user_prompt` switches
  between "initial proposal" and "revise addressing the Critic" based on whether a
  transcript exists.
- The **Critic**'s prompt asks for a single trailing verdict line; the supervisor
  parses it (see [06-orchestration.md](06-orchestration.md)).
- The **Summarizer** receives the full transcript and writes the final document.

## 5.3 The registry — `registry.py` (the extension point)

```python
class AgentRegistry:
    def register(self, agent) -> agent
    def get(self, name) -> BaseAgent
    def has(self, name) -> bool
    def all(self) -> list[BaseAgent]
    def catalog(self) -> list[{name, description}]   # level-1 metadata

registry = AgentRegistry()          # global instance
def register(agent): ...            # module-level convenience -> registry.register
def discover() -> AgentRegistry: ...
```

`discover()` imports every sibling module in the `agents` package (skipping
`base` and `registry`) using `pkgutil.iter_modules`. Importing a module runs its
`register(...)` call, so **any agent file placed in the package self-registers**.
The supervisor calls `registry.get("researcher")` etc.; it never imports the
concrete classes. That decoupling is what keeps the system "open to add agents."

## 5.4 Why instances, not classes?

Agents are stateless configuration, so the registry holds **instances**. This
keeps call sites simple (`registry.get("critic").stream(...)`) and means an agent
can be parameterised at construction if ever needed, without a metaclass dance.

### 🧪 Experiment — discover agents and read their metadata

```bash
python -c "
from agentic_kris.agents.registry import discover
reg = discover()
print('agents:', [a.name for a in reg.all()])
for e in reg.catalog():
    print(' -', e['name'], ':', e['description'][:70], '...')
print('researcher uses skills:', reg.get('researcher').skill_names)
print('researcher opts into RAG:', reg.get('researcher').retrieval_query(task='x', transcript='') is not None)
print('critic opts into RAG   :', reg.get('critic').retrieval_query(task='x', transcript='') is not None)
"
```

### 🧪 Experiment — run a single agent in isolation (no orchestration)

This drives just the Researcher with a fake provider and the in-memory retriever,
so you can see retrieval + skill injection + streaming without the loop:

```bash
python -c "
from agentic_kris.agents.registry import discover
from agentic_kris.skills.loader import SkillLoader
from agentic_kris.config import settings
from agentic_kris.rag.memory_store import InMemoryRetriever
from agentic_kris.llm.base import LLMProvider

class Fake(LLMProvider):
    name='fake'
    def stream(self, system, messages):
        # prove the skill body and retrieved context reached the prompt:
        assert 'web-research' in system.lower()
        yield '[researcher draft] '
        yield 'grounded in [K1].'

reg = discover(); L = SkillLoader(settings.skills_path)
researcher = reg.get('researcher')
got = {}
out = ''.join(researcher.stream(
    provider=Fake(), loader=L, task='How does hybrid RAG retrieval work?',
    retriever=InMemoryRetriever(), on_retrieve=lambda docs: got.setdefault('docs', docs),
))
print('retrieved docs:', len(got.get('docs', [])))
print('output       :', out)
"
```

### 🧪 Experiment — add a brand-new agent (auto-discovery)

```bash
cat > src/agentic_kris/agents/echo_agent.py <<'EOF'
from .base import BaseAgent
from .registry import register

class EchoAgent(BaseAgent):
    name = "echo"
    role = "Echo"
    description = "Repeats the task. Demonstrates zero-config agent discovery."
    system_prompt = "You echo."
    def build_user_prompt(self, *, task, transcript, context, user_note):
        return task

register(EchoAgent())
EOF

python -c "
from agentic_kris.agents.registry import discover
print('echo' in [a.name for a in discover().all()])   # True — no other code touched
"
rm src/agentic_kris/agents/echo_agent.py
```
