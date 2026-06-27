# 6. Orchestration

**Package:** `src/agentic_kris/orchestration/`

The supervisor turns a single user topic into a coordinated, multi-agent
conversation and emits a stream of events the UI renders live. It is **UI-
agnostic**: it imports nothing from Chainlit.

## 6.1 The loop policy — `workflow.py`

The convergence rules are factored out so they're easy to test and reuse.

```python
APPROVE = "APPROVE"; REVISE = "REVISE"

def parse_verdict(text) -> str:        # finds the last 'VERDICT' marker
    ... returns APPROVE / REVISE, defaulting to REVISE when unclear

@dataclass
class LoopState:
    max_rounds: int
    round: int = 0
    last_verdict: str = ""
    def should_continue(self) -> bool   # False once APPROVE or round == max_rounds
    @property converged -> bool         # last_verdict == APPROVE
    @property hit_cap   -> bool         # ran out of rounds without approval
```

Two deliberate choices:

- **Default to `REVISE`.** If the Critic's verdict is missing or ambiguous, the
  loop errs toward *more* scrutiny, not less.
- **Last-marker wins.** `parse_verdict` uses the *last* `VERDICT` occurrence, so
  a model that mentions the word earlier in its critique doesn't confuse it.

## 6.2 Events — `supervisor.py`

The supervisor yields `Event` dataclasses. One flat type keeps consumers simple:

| `kind` | Emitted when | Key fields |
| --- | --- | --- |
| `turn_start` | an agent turn begins | `role`, `round` |
| `retrieved` | the agent pulled RAG context | `role`, `round`, `docs` |
| `token` | a streamed chunk of agent output | `role`, `round`, `text` |
| `turn_end` | an agent turn completes | `role`, `round`, `content`, `verdict` |
| `status` | the loop ended; documenting begins | `text` |
| `final` | the Summarizer's documented answer | `role`, `content` |

(`Turn` is a small internal record — `role`, `round`, `content`, `verdict` — used
to accumulate the transcript.)

## 6.3 `Supervisor` construction

```python
Supervisor(
    *, provider, loader, registry,
    retriever=None, max_rounds=3, top_k=5,
)
```

It holds the shared dependencies and looks up its agents from the `registry` by
name — never by importing them.

## 6.4 Running one turn — `_run_turn`

`_run_turn(agent, *, task, transcript, round, user_note)` is a generator that:

1. yields `turn_start`;
2. calls `agent.stream(...)`, passing an `on_retrieve` callback that stashes any
   retrieved docs into a local dict;
3. **surfaces retrieval before the first token** — because `BaseAgent.stream`
   does retrieval at the top of the generator (before any provider tokens), the
   docs are already captured by the time the first token arrives, so a
   `retrieved` event is emitted exactly once, in order;
4. yields a `token` event per chunk;
5. parses the Critic's verdict (only for `agent.name == "critic"`) and yields
   `turn_end` with the full content + verdict.

This is the trick that lets a synchronous streaming generator also report a
side-effect (retrieval) at the right moment without callbacks leaking into the
event order.

## 6.5 The workflow — `run`

`Supervisor.run(task, *, user_note="")` is the whole default workflow:

```
state = LoopState(max_rounds)
loop:
    state.round += 1
    Researcher turn  → append to transcript          (yields its events)
    Critic turn      → parse verdict, append          (yields its events)
    state.last_verdict = verdict
    if not state.should_continue(): break
status event: "Discussion complete (Critic approved | reached the N-round cap)…"
Summarizer turn → yields a `final` event with the documented solution
```

Key properties:

- The Researcher sees the **growing transcript** each round, so round 2+ is a
  *revision* addressing the Critic.
- The loop stops the instant the Critic approves; otherwise it runs exactly
  `max_rounds` rounds.
- The `status` event tells the UI (and the user) *why* the loop ended.
- For the Summarizer, `_run_turn` yields `turn_start`/`token`s as normal but
  `run` converts its `turn_end` into a `final` event, so the UI can stream the
  final answer into the main message instead of a step.

## 6.6 Why a generator of events?

Returning an event stream (rather than, say, taking UI callbacks) means:

- the **same** supervisor drives the Chainlit UI, the tests, and any future CLI/
  API front-end;
- tests can assert on a flat list of events
  (see [10-testing-and-experiments.md](10-testing-and-experiments.md));
- the front-end decides how to render each event kind.

### 🧪 Experiment — run the whole workflow with a fake provider

No API key needed. This prints the event stream so you can see the loop:

```bash
python -c "
from agentic_kris.orchestration.supervisor import Supervisor
from agentic_kris.agents.registry import discover
from agentic_kris.skills.loader import SkillLoader
from agentic_kris.config import settings
from agentic_kris.rag.memory_store import InMemoryRetriever
from agentic_kris.llm.base import LLMProvider

class Fake(LLMProvider):
    name='fake'
    def __init__(self): self.n=0
    def stream(self, system, messages):
        # Key on the unique opener — the Researcher prompt also mentions 'Critic'.
        if 'You are the Critic' in system:
            self.n += 1
            yield 'Looks ' + ('good.' if self.n>=2 else 'incomplete.')
            yield '\nVERDICT: ' + ('APPROVE' if self.n>=2 else 'REVISE')
        elif 'You are the Researcher' in system:
            yield 'Proposal grounded in [K1].'
        else:
            yield '# Final\\n## Recommendation\\nDone.'

sup = Supervisor(provider=Fake(), loader=SkillLoader(settings.skills_path),
                 registry=discover(), retriever=InMemoryRetriever(), max_rounds=3)
for ev in sup.run('How does hybrid RAG retrieval work?'):
    if ev.kind == 'token':      # collapse token spam
        continue
    print(f'{ev.kind:11} role={ev.role:11} round={ev.round} '
          f'verdict={ev.verdict} docs={len(ev.docs)} {ev.text[:40]}')
"
```

Expected shape: round 1 Researcher (+retrieved) → Critic `REVISE` → round 2
Researcher → Critic `APPROVE` → `status` → Summarizer → `final`.

### 🧪 Experiment — force the round cap

Make the fake Critic always `REVISE` and watch it stop at `max_rounds`:

```bash
python -c "
from agentic_kris.orchestration.supervisor import Supervisor
from agentic_kris.agents.registry import discover
from agentic_kris.skills.loader import SkillLoader
from agentic_kris.config import settings
from agentic_kris.llm.base import LLMProvider

class AlwaysRevise(LLMProvider):
    name='fake'
    def stream(self, system, messages):
        if 'You are the Critic' in system: yield 'No.\\nVERDICT: REVISE'
        elif 'You are the Researcher' in system: yield 'draft'
        else: yield 'final doc'

sup = Supervisor(provider=AlwaysRevise(), loader=SkillLoader(settings.skills_path),
                 registry=discover(), max_rounds=2)
rounds = [e.round for e in sup.run('topic') if e.kind=='turn_end']
print('max round reached:', max(rounds))      # -> 2 (the cap)
"
```

### 🧪 Experiment — verdict parsing edge cases

```bash
python -c "
from agentic_kris.orchestration.workflow import parse_verdict
print(parse_verdict('blah VERDICT: APPROVE'))       # APPROVE
print(parse_verdict('I might APPROVE but...\nVERDICT: REVISE'))  # REVISE (last wins)
print(parse_verdict('no marker at all'))            # REVISE (safe default)
"
```
