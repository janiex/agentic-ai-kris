# 9. Request lifecycle — one topic, traced end to end

This ties every layer together. Follow a single user message,
*"How does hybrid RAG retrieval work?"*, from keypress to documented answer.

## 9.1 Sequence

```
User types topic
   │
   ▼
app.on_message(message)                          # app.py
   │  sup = cl.user_session.get("supervisor")
   ▼
Supervisor.run(task)  ── yields Events ──►  _aiter ──►  Chainlit rendering
   │
   ├─ ROUND 1 ───────────────────────────────────────────────────────────────
   │   _run_turn(Researcher)
   │      • Researcher.retrieval_query() -> task           # opts into RAG
   │      • InMemoryRetriever.retrieve(task, top_k)        # rag/memory_store.py
   │      • format_context(docs) -> "[K1]…"                # rag/retriever.py
   │      • build_system(): system_prompt + web-research SKILL body  # skills
   │      • provider.stream(system, [user])                # llm/*
   │      → emits: turn_start, retrieved, token*, turn_end
   │   _run_turn(Critic)
   │      • build_system(): system_prompt + critique SKILL body
   │      • provider.stream(...) -> "...\nVERDICT: REVISE"
   │      • parse_verdict() -> REVISE                      # orchestration/workflow.py
   │      → emits: turn_start, token*, turn_end(verdict=REVISE)
   │   LoopState.should_continue() -> True (REVISE, round<max)
   │   yield await_input  ──► UI: cl.AskUserMessage ──► gen.send(note)   # optional
   │      • if note: append Turn("User", …) to transcript (context kept)
   │
   ├─ ROUND 2 ───────────────────────────────────────────────────────────────
   │   Researcher sees the transcript -> REVISED proposal
   │   Critic -> "VERDICT: APPROVE"
   │   LoopState.should_continue() -> False (APPROVE)
   │
   ├─ status event: "Discussion complete (Critic approved). Documenting…"
   │
   └─ _run_turn(Summarizer)
          • build_system(): system_prompt + document-solution SKILL body
          • provider.stream(full transcript) -> final document
          → run() converts turn_end into a `final` event
```

## 9.2 Step-by-step with code references

1. **UI entry.** `on_message` (`app.py`) fetches the session's `Supervisor` and
   calls `sup.run(message.content)`, iterating it via `_aiter` so blocking LLM
   calls don't stall the event loop.

2. **Round loop.** `Supervisor.run` (`orchestration/supervisor.py`) increments
   `LoopState.round` and runs the Researcher then the Critic via `_run_turn`.

3. **Researcher retrieval.** Inside `BaseAgent.stream` (`agents/base.py`),
   `ResearcherAgent.retrieval_query` returns the task, so
   `retriever.retrieve(...)` runs and `format_context` builds the `[K1]` block.
   Because retrieval happens *before* the first token, `_run_turn` can emit the
   `retrieved` event in correct order (§6.4).

4. **Skill injection.** `build_system` calls
   `loader.prompt_for(self.skill_names)` (`skills/loader.py`), splicing the
   relevant `SKILL.md` body (level-2 disclosure) into the system prompt.

5. **LLM call.** `provider.stream(system, messages)` (`llm/…`) yields tokens; the
   chosen backend (Ollama or Anthropic) is whatever the factory built from
   settings.

6. **Critic verdict.** The Critic's trailing `VERDICT:` line is parsed by
   `parse_verdict` (`orchestration/workflow.py`); `LoopState.should_continue`
   decides whether to loop.

7. **Termination.** The loop ends on `APPROVE` or at `max_rounds`. `run` emits a
   `status` event explaining which, then runs the Summarizer.

8. **Documenting.** The Summarizer receives the whole transcript and writes the
   final document; `run` emits it as a `final` event, which the UI streams into
   the main answer message.

## 9.3 What each layer contributed

| Layer | Contribution to this request |
| --- | --- |
| Config | provided provider name, model, `max_review_rounds=3`, `top_k`, skills path |
| LLM | streamed each agent's tokens from the selected backend |
| Skills | injected `web-research` / `critique` / `document-solution` instructions |
| Agents | shaped each turn's prompt; the Researcher opted into RAG |
| RAG | returned `[K1]…` passages the Researcher grounded its proposal in |
| Orchestration | ran the loop, parsed the verdict, sequenced the agents, emitted events |
| UI | rendered steps, the verdict, and the streamed final answer |

### 🧪 Experiment — watch the lifecycle as an event log

The fake-provider experiment in
[06-orchestration.md](06-orchestration.md#-experiment--run-the-whole-workflow-with-a-fake-provider)
prints exactly this sequence of events. Run it to see rounds, the retrieval
event, the verdict transitions, the `status` line, and the `final` document — the
entire lifecycle, offline and in under a second.
