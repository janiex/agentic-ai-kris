# agentic-ai-kris — Full Documentation

This `DOC/` folder explains **how the system works, end to end**, with direct
references to the code and runnable examples for experimenting with each part.

Read it top-to-bottom for a complete mental model, or jump to the layer you care
about.

## Table of contents

| # | Document | What it covers |
| --- | --- | --- |
| 1 | [01-architecture.md](01-architecture.md) | The big picture: components, data flow, design principles |
| 2 | [02-configuration.md](02-configuration.md) | `Settings`, env vars, cross-platform paths |
| 3 | [03-llm-providers.md](03-llm-providers.md) | The provider abstraction, Ollama + Anthropic, the factory |
| 4 | [04-skills.md](04-skills.md) | Anthropic `SKILL.md` format, the loader, progressive disclosure |
| 5 | [05-agents-and-registry.md](05-agents-and-registry.md) | `BaseAgent`, the three agents, auto-discovery |
| 6 | [06-orchestration.md](06-orchestration.md) | The supervisor, the research↔critique loop, events |
| 7 | [07-rag.md](07-rag.md) | The retrieval seam, in-memory stub, pgvector roadmap |
| 8 | [08-chainlit-ui.md](08-chainlit-ui.md) | The chat UI, streaming, settings |
| 9 | [09-request-lifecycle.md](09-request-lifecycle.md) | A single request traced through every layer |
| 10 | [10-testing-and-experiments.md](10-testing-and-experiments.md) | How to test and poke at each part |
| 11 | [11-extending.md](11-extending.md) | Adding agents, skills, providers, workflows |

## Conventions used in these docs

- Code is referenced by **path + symbol**, e.g. *`get_provider()` in
  `src/agentic_kris/llm/factory.py`*. Paths are relative to the project root.
- **Experiment boxes** (`### 🧪 Experiment`) contain commands or Python snippets
  you can paste into an activated virtualenv to see a piece of the system run in
  isolation.
- All Python snippets assume you are at the project root with the venv active:
  ```bash
  cd /Users/kris/Projects/agentic-ai-kris
  source .venv/bin/activate     # Windows: .venv\Scripts\Activate.ps1
  ```

## 30-second mental model

A user sends a **topic**. A **Supervisor** orchestrates three **agents** in a
fixed default workflow:

```
Researcher → Critic → (loop ≤ 3 rounds) → Summarizer documents the result
```

Each agent is thin configuration over a shared `BaseAgent`; each can load
**Skills** (Anthropic `SKILL.md` packages) and retrieve from a **RAG** layer. The
LLM backend (local **Ollama** or **Anthropic Claude**) is swappable at runtime.
Everything streams to a **Chainlit** chat UI. New agents and skills are added by
dropping a file/folder — nothing else changes.
