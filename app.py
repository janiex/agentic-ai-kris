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


async def _aiter(gen):
    """Iterate a blocking sync generator without stalling the event loop."""
    while True:
        item = await asyncio.to_thread(next, gen, _SENTINEL)
        if item is _SENTINEL:
            break
        yield item


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
    step: cl.Step | None = None
    final_msg: cl.Message | None = None
    documenting = False

    try:
        async for ev in _aiter(gen):
            if ev.kind == "status":
                documenting = True
                await cl.Message(content=f"_{ev.text}_").send()
                final_msg = cl.Message(content="", author="Summarizer")

            elif ev.kind == "turn_start":
                if not documenting:
                    step = cl.Step(name=f"{ev.role} · round {ev.round}", type="llm")
                    await step.send()

            elif ev.kind == "retrieved":
                n = len(ev.docs)
                srcs = ", ".join(
                    str(d.metadata.get("source", "?")) for d in ev.docs
                ) or "—"
                if step is not None:
                    await step.stream_token(
                        f"🔎 _Retrieved {n} passage(s) from RAG: {srcs}_\n\n"
                    )

            elif ev.kind == "token":
                if documenting and final_msg is not None:
                    await final_msg.stream_token(ev.text)
                elif step is not None:
                    await step.stream_token(ev.text)

            elif ev.kind == "turn_end":
                if step is not None:
                    if ev.verdict:
                        await step.stream_token(f"\n\n**VERDICT: {ev.verdict}**")
                    await step.update()
                    step = None

            elif ev.kind == "final":
                if final_msg is not None:
                    await final_msg.update()
    except Exception as e:  # noqa: BLE001
        await cl.Message(content=f"⚠️ Error while running the agents: {e}").send()
