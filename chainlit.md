# agentic-ai-kris 🤖

An extensible multi-agent system. Give it a topic and watch three specialists
collaborate:

- 🔬 **Researcher** — studies the topic, grounding its proposal in retrieved knowledge (RAG).
- 🧐 **Critic** — reviews the proposal and votes `APPROVE` / `REVISE`.
- 📝 **Summarizer** — documents the consolidated solution once the discussion settles.

The Researcher and Critic loop up to **3 rounds**, then the Summarizer writes the
final answer.

Use the ⚙️ settings to switch the LLM backend (local **Ollama** or **Anthropic
Claude**), pick a model, or toggle RAG retrieval.

> Adding agents/skills is easy — drop a module under `src/agentic_kris/agents/`
> or a folder under `skills/`. See the README.
