# 8. The Chainlit UI

**Files:** `app.py`, `chainlit.md` · **Launchers:** `run.py`, `run.sh`

The UI is a thin adapter: it builds a `Supervisor`, consumes its event stream,
and renders each event kind. All the logic lives below it.

## 8.1 Lifecycle hooks

| Hook | When | What it does |
| --- | --- | --- |
| `@cl.on_chat_start` | a chat session opens | sends the settings widgets + a welcome, then builds the supervisor |
| `@cl.on_settings_update` | the user changes ⚙️ settings | rebuilds the supervisor with the new provider/model/key/RAG |
| `@cl.on_message` | the user sends a topic | runs the supervisor and renders its events |

## 8.2 Settings widgets — `_settings_widgets()`

A `cl.ChatSettings` with four inputs:

- `provider` — a `Select` over `available_providers()` (`anthropic`, `ollama`);
- `model` — a `TextInput` (blank → provider default);
- `api_key` — a `TextInput` for a session-only Anthropic key (blank → `.env`);
- `use_rag` — a `Switch` (defaults **on**, so the demo shows retrieval).

## 8.3 Building the supervisor — `_build_supervisor(values)`

Maps the settings dict to dependencies:

```python
provider  = get_provider(values['provider'], model=values['model'] or None,
                         api_key=values['api_key'] or None)
loader    = SkillLoader(settings.skills_path)
registry  = discover()
retriever = InMemoryRetriever() if values.get('use_rag', True) else None
Supervisor(provider=..., loader=..., registry=..., retriever=...,
           max_rounds=settings.max_review_rounds, top_k=settings.retrieval_top_k)
```

`_rebuild(values)` wraps this in try/except: on success it stores the supervisor
in `cl.user_session` and posts "✅ Backend ready…"; on failure (e.g. missing
Anthropic key) it stores `None` and posts a clear warning, so the app never
crashes on a bad backend — it just tells you to fix settings.

## 8.4 Bridging sync → async — `_aiter`

`Supervisor.run` is a **synchronous** generator doing blocking network I/O, but
Chainlit handlers are **async**. `_aiter` iterates the generator one item at a
time on a worker thread so the event loop stays responsive:

```python
async def _aiter(gen):
    while True:
        item = await asyncio.to_thread(next, gen, _SENTINEL)
        if item is _SENTINEL: break
        yield item
```

This is why a slow LLM call doesn't freeze the UI.

## 8.5 Rendering the event stream — `on_message`

Each `Event.kind` maps to a UI action:

| Event | UI action |
| --- | --- |
| `turn_start` | open a `cl.Step` named `"<role> · round N"` (skipped once documenting) |
| `retrieved` | stream a `🔎 Retrieved N passage(s)…` note into the current step |
| `token` | `step.stream_token(...)` — or, once documenting, stream into the final `cl.Message` |
| `turn_end` | append the `VERDICT` line (if any) and `step.update()` |
| `status` | post the "Discussion complete…" line and open the final message |
| `final` | `final_msg.update()` to finalise the documented answer |

So the Researcher and Critic turns appear as **collapsible steps**, and the
Summarizer's output streams into the **main answer message**. The whole
`on_message` body is wrapped in try/except so any backend error surfaces as a
chat message instead of a stack trace.

## 8.6 Launchers

- `run.py` — pure-Python, cross-platform; shells out to
  `python -m chainlit run app.py --port $PORT`. `--watch` adds auto-reload.
- `run.sh` — Unix convenience wrapper that activates `.venv` then calls `run.py`.
- `chainlit.md` — the welcome screen shown in the UI.

### 🧪 Experiment — start the UI and probe it without a browser

```bash
PORT=8780 python run.py > /tmp/kris-ui.log 2>&1 &
# wait for readiness
for i in $(seq 1 20); do
  [ "$(curl -s -o /dev/null -w '%{http_code}' http://localhost:8780/)" = "200" ] && break
  sleep 1
done
curl -s -o /dev/null -w 'root HTTP %{http_code}\n' http://localhost:8780/
grep -c Traceback /tmp/kris-ui.log    # expect 0 on Python 3.10–3.13
pkill -f "chainlit run"
```

### 🧪 Experiment — drive a full chat

```bash
# Anthropic: put ANTHROPIC_API_KEY in .env, or
# Ollama: `ollama pull llama3.1` and pick 'ollama' in the ⚙️ settings
python run.py        # open http://localhost:8000 and type a topic
```

You should see: a **Researcher** step (with a 🔎 retrieval note), a **Critic**
step ending in a `VERDICT`, possibly more rounds, then the **Summarizer**'s
documented answer streaming as the main reply.

> **Python version:** the Chainlit/uvicorn/anyio stack does not yet support
> Python 3.14. Use 3.10–3.13. The project's `.venv` was created with 3.12 via
> `uv` for exactly this reason; `requires-python` in `pyproject.toml` enforces
> `<3.14`.
