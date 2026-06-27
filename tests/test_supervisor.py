"""End-to-end orchestration with a fake provider and the in-memory retriever."""
from __future__ import annotations

from agentic_kris.llm.base import LLMProvider
from agentic_kris.orchestration.supervisor import Supervisor
from agentic_kris.rag.memory_store import InMemoryRetriever

from conftest import FakeProvider


def _run(provider, loader, registry, max_rounds=3):
    sup = Supervisor(
        provider=provider,
        loader=loader,
        registry=registry,
        retriever=InMemoryRetriever(),
        max_rounds=max_rounds,
    )
    return list(sup.run("How does RAG work?"))


def _rounds(events):
    return max((e.round for e in events if e.kind == "turn_end"), default=0)


def test_loop_stops_on_approve(loader, registry):
    events = _run(FakeProvider(["APPROVE"]), loader, registry)
    assert _rounds(events) == 1
    assert any(e.kind == "final" and e.content for e in events)


def test_loop_caps_at_max_rounds(loader, registry):
    events = _run(FakeProvider(["REVISE", "REVISE", "REVISE", "REVISE"]), loader, registry)
    assert _rounds(events) == 3
    # Still produces a documented final answer at the cap.
    assert any(e.kind == "final" for e in events)


def test_researcher_retrieval_is_surfaced(loader, registry):
    events = _run(FakeProvider(["APPROVE"]), loader, registry)
    retrieved = [e for e in events if e.kind == "retrieved"]
    assert retrieved, "expected the Researcher's RAG retrieval to emit an event"
    assert retrieved[0].role == "Researcher"


def test_tokens_stream(loader, registry):
    events = _run(FakeProvider(["APPROVE"]), loader, registry)
    assert any(e.kind == "token" and e.text for e in events)


# ── interactive guidance on REVISE ───────────────────────────────────────────
class CapturingProvider(LLMProvider):
    """Like FakeProvider but records each Researcher user-prompt it receives."""

    name = "capturing"

    def __init__(self, verdicts):
        self.verdicts, self.i = list(verdicts), 0
        self.researcher_prompts: list[str] = []

    def stream(self, system, messages):
        user = messages[-1]["content"]
        if "You are the Critic" in system:
            v = self.verdicts[min(self.i, len(self.verdicts) - 1)]
            self.i += 1
            yield f"review\nVERDICT: {v}"
        elif "You are the Researcher" in system:
            self.researcher_prompts.append(user)
            yield "proposal citing [K1]"
        else:
            yield "# Final\n## Recommendation\ndone"


def _drive(sup, task, note_at_pause=""):
    """Drive the resumable generator, sending `note_at_pause` at each pause."""
    gen = sup.run(task)
    events = []
    try:
        ev = gen.send(None)
        while True:
            events.append(ev)
            ev = gen.send(note_at_pause if ev.kind == "await_input" else None)
    except StopIteration:
        pass
    return events


def test_await_input_emitted_on_every_revise(loader, registry):
    sup = Supervisor(provider=FakeProvider(["REVISE", "REVISE", "REVISE"]),
                     loader=loader, registry=registry, max_rounds=2)
    events = _drive(sup, "topic")   # skip every pause
    awaits = [e for e in events if e.kind == "await_input"]
    # max_rounds=2, always REVISE, all skipped: a pause each round (mid + cap).
    assert len(awaits) == 2
    assert awaits[0].at_cap is False           # round 1: below the cap
    assert awaits[1].at_cap is True            # round 2: the cap checkpoint
    assert _rounds(events) == 2                # skipping the cap finalizes at 2


def test_cap_continues_with_user_input(loader, registry):
    prov = CapturingProvider(["REVISE", "REVISE", "APPROVE"])
    sup = Supervisor(provider=prov, loader=loader, registry=registry,
                     retriever=InMemoryRetriever(), max_rounds=2)
    # Provide input at every pause, including the cap → the loop extends past it.
    events = _drive(sup, "topic", note_at_pause="keep refining the cost model")
    assert any(e.kind == "await_input" and e.at_cap for e in events)
    # Extended beyond the original 2-round cap to a 3rd Researcher round...
    assert len(prov.researcher_prompts) >= 3
    # ...and the cap-time guidance reached that extra round (context preserved).
    assert "keep refining the cost model" in prov.researcher_prompts[2]
    assert any(e.kind == "final" for e in events)


def test_cap_finalizes_when_skipped(loader, registry):
    prov = CapturingProvider(["REVISE", "REVISE", "REVISE"])
    sup = Supervisor(provider=prov, loader=loader, registry=registry,
                     retriever=InMemoryRetriever(), max_rounds=2)
    events = _drive(sup, "topic")              # skip the cap
    assert _rounds(events) == 2
    assert len(prov.researcher_prompts) == 2   # never extended
    assert any(e.kind == "final" for e in events)


def test_no_await_input_when_approved_first_round(loader, registry):
    sup = Supervisor(provider=FakeProvider(["APPROVE"]), loader=loader,
                     registry=registry, retriever=InMemoryRetriever(), max_rounds=3)
    events = _drive(sup, "topic")
    assert not any(e.kind == "await_input" for e in events)
    assert any(e.kind == "final" for e in events)


def test_guidance_reaches_next_round_as_context(loader, registry):
    prov = CapturingProvider(["REVISE", "APPROVE"])
    sup = Supervisor(provider=prov, loader=loader, registry=registry,
                     retriever=InMemoryRetriever(), max_rounds=3)
    events = _drive(sup, "topic", note_at_pause="focus on cost")
    assert any(e.kind == "await_input" for e in events)
    # The round-2 Researcher prompt must carry the injected guidance.
    assert len(prov.researcher_prompts) >= 2
    assert "focus on cost" in prov.researcher_prompts[1]


def test_skipping_guidance_continues_cleanly(loader, registry):
    prov = CapturingProvider(["REVISE", "APPROVE"])
    sup = Supervisor(provider=prov, loader=loader, registry=registry,
                     retriever=InMemoryRetriever(), max_rounds=3)
    events = _drive(sup, "topic", note_at_pause="")   # user skips
    assert any(e.kind == "final" for e in events)
    # No guidance text leaks into the next round when skipped.
    assert "focus on cost" not in prov.researcher_prompts[1]
