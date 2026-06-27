"""Chainlit chat UI for agentic-ai-kris.

A user types a topic; the Supervisor runs the Researcher<->Critic loop (each turn
shown as a live step) and the Summarizer documents the consolidated solution as
the final answer. Provider, model, and RAG can be changed from chat settings.

Run with:  chainlit run app.py      (or: python run.py)
"""
from __future__ import annotations

import asyncio

import chainlit as cl

from agentic_kris.agents.registry import discover
from agentic_kris.config import settings
from agentic_kris.llm.factory import available_providers, get_provider
from agentic_kris.orchestration.supervisor import Supervisor
from agentic_kris.rag.memory_store import InMemoryRetriever
from agentic_kris.skills.loader import SkillLoader

_SENTINEL = object()


async def _render_event(ev, ui: dict) -> None:
    """Render one supervisor Event into the Chainlit UI.

    `ui` carries the mutable rendering state (current step, the final answer
    message, and whether we've reached the documenting phase).
    """
    if ev.kind == "status":
        ui["documenting"] = True
        await cl.Message(content=f"_{ev.text}_").send()
        ui["final_msg"] = cl.Message(content="", author="Summarizer")

    elif ev.kind == "turn_start":
        if not ui["documenting"]:
            ui["step"] = cl.Step(name=f"{ev.role} · round {ev.round}", type="llm")
            await ui["step"].send()

    elif ev.kind == "retrieved":
        n = len(ev.docs)
        srcs = ", ".join(str(d.metadata.get("source", "?")) for d in ev.docs) or "—"
        if ui["step"] is not None:
            await ui["step"].stream_token(
                f"🔎 _Retrieved {n} passage(s) from RAG: {srcs}_\n\n"
            )

    elif ev.kind == "token":
        if ui["documenting"] and ui["final_msg"] is not None:
            await ui["final_msg"].stream_token(ev.text)
        elif ui["step"] is not None:
            await ui["step"].stream_token(ev.text)

    elif ev.kind == "turn_end":
        if ui["step"] is not None:
            if ev.verdict:
                await ui["step"].stream_token(f"\n\n**VERDICT: {ev.verdict}**")
            await ui["step"].update()
            ui["step"] = None

    elif ev.kind == "final":
        if ui["final_msg"] is not None:
            await ui["final_msg"].update()


async def _collect_guidance(ev) -> str:
    """Pause the loop and ask the user for input.

    Below the cap this is optional steering; at the cap (``ev.at_cap``) it decides
    whether the discussion *continues* (input) or *finalizes* (skip). Returns the
    user's note, or "" if they skip / time out.
    """
    if ev.at_cap:
        prompt = (
            f"🔚 The {ev.round}-round limit is reached and the Critic still wants "
            f"changes. Send input to **continue** the discussion (the full prior "
            f"context is kept), or send `skip` to finalize the answer now."
        )
    else:
        prompt = (
            f"🧭 The Critic requested a revision after round {ev.round}. "
            f"Reply with guidance to steer round {ev.round + 1}, or send `skip` "
            "to continue without it."
        )
    res = await cl.AskUserMessage(content=prompt, timeout=180).send()
    note = ((res or {}).get("output") or "").strip()
    if not note or note.lower() == "skip":
        return ""
    label = (
        f"▶️ Continuing (round {ev.round + 1}) with: {note}"
        if ev.at_cap
        else f"🧭 Guidance for round {ev.round + 1}: {note}"
    )
    await cl.Message(author="You", content=label).send()
    return note


def _settings_widgets() -> cl.ChatSettings:
    providers = available_providers()
    return cl.ChatSettings(
        [
            cl.input_widget.Select(
                id="provider",
                label="LLM backend",
                values=providers,
                initial_index=providers.index(settings.llm_provider)
                if settings.llm_provider in providers
                else 0,
            ),
            cl.input_widget.TextInput(
                id="model",
                label="Model (blank = default for provider)",
                initial="",
            ),
            cl.input_widget.TextInput(
                id="api_key",
                label="Anthropic API key (session only; blank uses .env)",
                initial="",
            ),
            cl.input_widget.Switch(
                id="use_rag",
                label="Use RAG retrieval (in-memory stub)",
                initial=True,
            ),
        ]
    )


def _build_supervisor(values: dict) -> Supervisor:
    provider = get_provider(
        values.get("provider") or settings.llm_provider,
        model=(values.get("model") or None),
        api_key=(values.get("api_key") or None),
    )
    loader = SkillLoader(settings.skills_path)
    registry = discover()
    retriever = InMemoryRetriever() if values.get("use_rag", True) else None
    return Supervisor(
        provider=provider,
        loader=loader,
        registry=registry,
        retriever=retriever,
        max_rounds=settings.max_review_rounds,
        top_k=settings.retrieval_top_k,
    )


async def _rebuild(values: dict) -> None:
    cl.user_session.set("settings_values", values)
    try:
        sup = await asyncio.to_thread(_build_supervisor, values)
        cl.user_session.set("supervisor", sup)
        await cl.Message(
            content=f"✅ Backend ready: **{sup.provider.name}** "
            f"· max {sup.max_rounds} review rounds "
            f"· RAG {'on' if sup.retriever else 'off'}."
        ).send()
    except Exception as e:  # noqa: BLE001
        cl.user_session.set("supervisor", None)
        await cl.Message(content=f"⚠️ Could not initialise the backend: {e}").send()


@cl.on_chat_start
async def on_chat_start():
    await _settings_widgets().send()
    await cl.Message(
        content=(
            "👋 **agentic-ai-kris** — give me a topic to work on.\n\n"
            "A **Researcher** studies it, a **Critic** reviews it (looping up to "
            f"{settings.max_review_rounds}× ), and a **Summarizer** documents the "
            "consolidated solution. Adjust the backend or RAG in ⚙️ settings."
        )
    ).send()
    await _rebuild(
        {
            "provider": settings.llm_provider,
            "model": "",
            "api_key": "",
            "use_rag": True,
        }
    )


@cl.on_settings_update
async def on_settings_update(values: dict):
    await _rebuild(values)


@cl.on_message
async def on_message(message: cl.Message):
    sup: Supervisor | None = cl.user_session.get("supervisor")
    if sup is None:
        await cl.Message(
            content="The backend isn't ready. Open ⚙️ settings and check your "
            "provider / API key."
        ).send()
        return

    gen = sup.run(message.content)
    ui = {"step": None, "final_msg": None, "documenting": False}

    def advance(value):
        # Drive the resumable generator; send() lets us feed guidance back in.
        try:
            return gen.send(value)
        except StopIteration:
            return _SENTINEL

    try:
        ev = await asyncio.to_thread(advance, None)   # prime the generator
        while ev is not _SENTINEL:
            if ev.kind == "await_input":
                note = await _collect_guidance(ev)
                ev = await asyncio.to_thread(advance, note)
                continue
            await _render_event(ev, ui)
            ev = await asyncio.to_thread(advance, None)
    except Exception as e:  # noqa: BLE001
        await cl.Message(content=f"⚠️ Error while running the agents: {e}").send()
