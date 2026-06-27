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

## 8.4 Bridging sync → async — the send-driving loop

`Supervisor.run` is a **synchronous, resumable** generator doing blocking network
I/O, but Chainlit handlers are **async**. `on_message` drives it one event at a
time on a worker thread (so the event loop stays responsive) and uses
`generator.send(...)` so it can feed user guidance back in at a pause:

```python
def advance(value):
    try:
        return gen.send(value)        # send(None) == next(); send(note) resumes a pause
    except StopIteration:
        return _SENTINEL

ev = await asyncio.to_thread(advance, None)     # prime
while ev is not _SENTINEL:
    if ev.kind == "await_input":
        note = await _collect_guidance(ev)      # cl.AskUserMessage (see 8.5a)
        ev = await asyncio.to_thread(advance, note)
        continue
    await _render_event(ev, ui)
    ev = await asyncio.to_thread(advance, None)
```

This is why a slow LLM call doesn't freeze the UI, and why the user can steer a
revision without the discussion losing context (the generator stays suspended in
memory across the prompt).

## 8.5 Rendering the event stream — `_render_event`

Each non-`await_input` event maps to a UI action (in `_render_event(ev, ui)`,
where `ui` holds the current step / final message / documenting flag):

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
`on_message` loop is wrapped in try/except so any backend error surfaces as a
chat message instead of a stack trace.

## 8.5a Collecting guidance — `_collect_guidance`

The `await_input` event is handled specially (not in `_render_event`): the loop
calls `_collect_guidance(ev)`, which prompts the user with `cl.AskUserMessage`
and returns their note (or `""` if skipped / timed out). It branches on
`ev.at_cap`:

```python
if ev.at_cap:                       # round limit reached → continue or finalize
    prompt = (f"🔚 The {ev.round}-round limit is reached and the Critic still "
              "wants changes. Send input to **continue** the discussion (full "
              "prior context kept), or send `skip` to finalize now.")
else:                               # below the cap → optional steering
    prompt = (f"🧭 The Critic requested a revision after round {ev.round}. "
              f"Reply with guidance to steer round {ev.round + 1}, or send `skip`.")
res = await cl.AskUserMessage(content=prompt, timeout=180).send()
note = ((res or {}).get("output") or "").strip()
if not note or note.lower() == "skip":
    return ""
# echo an accepted note back into the thread (▶️ Continuing… / 🧭 Guidance…)
return note
```

The returned note is sent back into the generator via `advance(note)` (§8.4):

- **Below the cap** — the supervisor folds it into the next round and continues.
- **At the cap** — a non-empty note makes the supervisor grant one more round and
  continue; an empty reply finalizes. **Continuing past the cap loses no
  context:** the generator is merely *suspended* at the pause (not torn down), so
  the entire prior discussion — all earlier rounds — is still in memory and keeps
  growing in the same transcript.

## 8.6 Launchers and lifecycle

`run.py` is a pure-Python, cross-platform lifecycle manager (no extra deps). The
port comes from `$PORT` (default 8000) and applies to every command.

| Command | What it does |
| --- | --- |
| `python run.py` / `python run.py start` | start the server in the **foreground** (Ctrl+C to stop); `--watch` adds auto-reload |
| `python run.py status` | print `● running … (PID …)` or `○ stopped`; exit code 0/1 |
| `python run.py stop` | stop the server on `$PORT` gracefully (SIGTERM→SIGKILL; `taskkill /T /F` on Windows) and confirm the port is free |
| `python run.py restart` | `stop` then `start` |

How it works:

- **start** refuses to launch if `$PORT` is already in use, spawns
  `python -m chainlit run app.py --port $PORT`, and records `"<pid> <port>"` in
  `.run.pid` (gitignored). On foreground exit / Ctrl+C it cleans the pidfile.
- **stop / status** locate the live process by **port** first — `lsof -ti
  tcp:$PORT -sTCP:LISTEN` on Unix, `netstat -ano` on Windows — and fall back to
  `.run.pid` if those tools aren't present. `status` also does a quick socket
  connect to `127.0.0.1:$PORT` to decide up/down.

`run.sh` is a Unix wrapper that activates `.venv` and forwards all arguments, so
`./run.sh stop`, `./run.sh status`, etc. work too. `chainlit.md` is the welcome
screen shown in the UI.

> **Foreground vs background.** In the foreground, `Ctrl+C` is the natural stop.
> `stop` exists for servers launched in the background (`python run.py start &`)
> or from another terminal. The in-memory RAG stub lives inside the process, so
> stopping the process is a complete shutdown — there are no leftover workers.
> The future Postgres+pgvector store is separate: `docker compose down`.

### 🧪 Experiment — start the UI and probe it without a browser

```bash
export PORT=8780
python run.py start > /tmp/kris-ui.log 2>&1 &
# wait for readiness
for i in $(seq 1 20); do python run.py status >/dev/null 2>&1 && break; sleep 1; done
python run.py status                          # ● running … (PID …)
curl -s -o /dev/null -w 'root HTTP %{http_code}\n' http://localhost:8780/
grep -c Traceback /tmp/kris-ui.log            # expect 0 on Python 3.10–3.13
python run.py stop                            # ■ stopped, port freed
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
