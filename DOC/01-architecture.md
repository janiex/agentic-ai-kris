# 1. Architecture

## 1.1 The big picture

```
        ┌──────────────────── Chainlit UI (app.py) ─────────────────────┐
        │  chat input · live per-agent steps · provider/RAG settings     │
        └────────────────────────────┬───────────────────────────────────┘
                                      │  Event stream (sync generator)
                       ┌──────────────▼───────────────┐
                       │   Supervisor                  │   orchestration/
                       │   Researcher ⇄ Critic (≤3)    │   supervisor.py
                       │      → Summarizer documents    │   workflow.py
                       └───┬───────────────────────┬────┘
            AgentRegistry  │                       │  shared dependencies
          (discovery)      │                       │
        ┌──────────────────▼───────┐   ┌───────────▼──────────────────────┐
        │ Researcher / Critic /    │   │ LLMProvider   ·   Retriever       │
        │ Summarizer  (BaseAgent)  │   │ (ollama|       (in-memory stub →  │
        │   uses → SkillLoader     │   │  anthropic)     pgvector planned) │
        └──────────┬───────────────┘   └───────────────────────────────────┘
                   │ loads SKILL.md packages
        ┌──────────▼───────────────┐
        │ skills/  (web-research,   │
        │ critique, document-...)   │
        └───────────────────────────┘
```

## 1.2 Component responsibilities

| Layer | Package / file | Responsibility |
| --- | --- | --- |
| **Config** | `src/agentic_kris/config.py` | One env-driven `Settings` object; cross-platform paths |
| **LLM** | `src/agentic_kris/llm/` | Provider-agnostic `stream`/`complete`; Ollama + Anthropic; a factory |
| **Skills** | `src/agentic_kris/skills/` + `skills/` | Parse/validate `SKILL.md`, serve the 3 disclosure levels |
| **Agents** | `src/agentic_kris/agents/` | `BaseAgent` + 3 specialists + a self-registering registry |
| **Orchestration** | `src/agentic_kris/orchestration/` | The supervisor workflow and its loop policy; emits `Event`s |
| **RAG** | `src/agentic_kris/rag/` | A stable `Retriever` interface; stub now, pgvector later |
| **UI** | `app.py`, `chainlit.md` | Chat front-end; consumes the supervisor's event stream |
| **Entry** | `run.py`, `run.sh` | Cross-platform launchers |

## 1.3 Dependency direction

Dependencies point **inward and downward**, never up:

```
app.py  ──►  orchestration  ──►  agents  ──►  llm
   │              │               │     └──►  skills
   │              │               └──►  rag
   └──────────────┴──────────────────►  config   (everything reads config)
```

- The **UI** knows about the supervisor but the supervisor knows nothing about
  Chainlit — it only yields plain `Event` dataclasses. That is what makes the
  core testable without a browser (see [10-testing-and-experiments.md](10-testing-and-experiments.md)).
- The **supervisor** depends on the *registry abstraction*, never on concrete
  agent classes. Adding an agent does not touch the supervisor.
- **Agents** depend on the `LLMProvider` interface and the `Retriever` interface,
  never on concrete implementations. Swapping Ollama↔Anthropic or
  stub-RAG↔pgvector changes nothing in agent code.

## 1.4 Design principles

1. **Open for extension, closed for modification.** New agents/skills are
   *additive* — a dropped file is auto-discovered (`AgentRegistry.discover()`,
   `SkillLoader.reload()`). This is the core requirement of the system.
2. **Progressive disclosure everywhere.** Skills and agents expose cheap level-1
   metadata (`name` + `description`); heavy content (instructions, resources,
   retrieved passages) is loaded only when actually used. See [04-skills.md](04-skills.md).
3. **Interfaces over implementations.** `LLMProvider` and `Retriever` are ABCs/
   Protocols; everything else codes against them.
4. **UI-agnostic core.** The orchestration layer yields an event stream; any
   front-end (Chainlit today, a CLI or API tomorrow) can drive it.
5. **Cross-platform by construction.** `pathlib` for every path, `sys.executable`
   for subprocess calls, a pure-Python launcher. Runs on Linux/macOS/Windows.

## 1.5 The default workflow in one sentence

> The **Researcher** proposes a grounded solution; the **Critic** reviews it and
> votes `APPROVE`/`REVISE`; they loop until approval or a 3-round cap; then the
> **Summarizer** documents the consolidated outcome.

The full trace of one request is in
[09-request-lifecycle.md](09-request-lifecycle.md).
