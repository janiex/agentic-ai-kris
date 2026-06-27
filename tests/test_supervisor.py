"""End-to-end orchestration with a fake provider and the in-memory retriever."""
from __future__ import annotations

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
