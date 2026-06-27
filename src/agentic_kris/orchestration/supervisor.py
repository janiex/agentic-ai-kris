"""Supervisor — orchestrates the default research<->critique workflow.

Flow for one request:
  1. Researcher studies the topic (round 1), pulling RAG context.
  2. Critic reviews -> verdict (APPROVE | REVISE).
  3. Loop Researcher->Critic until APPROVE or MAX_REVIEW_ROUNDS, whichever first.
  4. Summarizer observes the whole transcript and documents the final solution.

The supervisor is UI-agnostic: it yields a stream of :class:`Event` objects that
any front-end (the Chainlit app, the tests) consumes. It depends on the
:class:`AgentRegistry`, not concrete agent classes, so the workflow stays open to
new agents.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterator, List, Optional

from ..agents.base import BaseAgent
from ..agents.registry import AgentRegistry
from ..llm.base import LLMProvider
from ..rag.retriever import RetrievedDoc, Retriever
from ..skills.loader import SkillLoader
from .workflow import LoopState, parse_verdict


# ── events the UI/tests consume ──────────────────────────────────────────────
@dataclass
class Event:
    kind: str                       # turn_start | retrieved | token | turn_end | final | status
    role: str = ""
    round: int = 0
    text: str = ""                  # token text (token) or message (status)
    content: str = ""               # full turn text (turn_end / final)
    verdict: str = ""
    docs: List[RetrievedDoc] = field(default_factory=list)


@dataclass
class Turn:
    role: str
    round: int
    content: str
    verdict: str = ""


class Supervisor:
    def __init__(
        self,
        *,
        provider: LLMProvider,
        loader: SkillLoader,
        registry: AgentRegistry,
        retriever: Optional[Retriever] = None,
        max_rounds: int = 3,
        top_k: int = 5,
    ):
        self.provider = provider
        self.loader = loader
        self.registry = registry
        self.retriever = retriever
        self.max_rounds = max_rounds
        self.top_k = top_k

    # ── transcript helper ────────────────────────────────────────────────────
    @staticmethod
    def _render(transcript: List[Turn]) -> str:
        return "\n\n".join(
            f"--- {t.role} (round {t.round}) ---\n{t.content}" for t in transcript
        )

    # ── run one agent turn, streaming its tokens as events ───────────────────
    def _run_turn(
        self, agent: BaseAgent, *, task: str, transcript: List[Turn],
        round: int, user_note: str,
    ) -> Iterator[Event]:
        yield Event("turn_start", role=agent.role, round=round)

        captured: dict = {}
        gen = agent.stream(
            provider=self.provider,
            loader=self.loader,
            task=task,
            transcript=self._render(transcript),
            user_note=user_note,
            retriever=self.retriever,
            top_k=self.top_k,
            on_retrieve=lambda docs: captured.__setitem__("docs", docs),
        )

        buf: List[str] = []
        announced = False
        for tok in gen:
            # Retrieval (if any) runs before the first token; surface it once.
            if not announced and "docs" in captured:
                yield Event("retrieved", role=agent.role, round=round, docs=captured["docs"])
                announced = True
            buf.append(tok)
            yield Event("token", role=agent.role, round=round, text=tok)
        if not announced and "docs" in captured:
            yield Event("retrieved", role=agent.role, round=round, docs=captured["docs"])

        content = "".join(buf)
        verdict = parse_verdict(content) if agent.name == "critic" else ""
        # Stash the parsed verdict so the caller can read it off the event.
        yield Event(
            "turn_end", role=agent.role, round=round, content=content, verdict=verdict
        )

    # ── the orchestrated workflow ────────────────────────────────────────────
    def run(self, task: str, *, user_note: str = "") -> Iterator[Event]:
        """Drive the workflow, yielding events.

        This is a *resumable* generator. When the Critic votes REVISE and another
        round will run, it yields an ``await_input`` event **as an expression**
        and receives the user's optional guidance via ``generator.send(note)``.
        A plain ``for``/``list`` iteration sends ``None`` at that point, i.e. it
        simply skips the prompt — so non-interactive callers behave as before.
        The transcript accumulates across the whole loop, so the discussion
        context is retained when the user contributes.
        """
        researcher = self.registry.get("researcher")
        critic = self.registry.get("critic")
        summarizer = self.registry.get("summarizer")

        transcript: List[Turn] = []
        state = LoopState(max_rounds=self.max_rounds)
        pending_note = user_note          # guidance to emphasise for this round

        while True:
            state.round += 1

            # Researcher proposes / revises.
            content = ""
            for ev in self._run_turn(
                researcher, task=task, transcript=transcript,
                round=state.round, user_note=pending_note,
            ):
                if ev.kind == "turn_end":
                    content = ev.content
                yield ev
            transcript.append(Turn(researcher.role, state.round, content))

            # Critic reviews and votes.
            content, verdict = "", ""
            for ev in self._run_turn(
                critic, task=task, transcript=transcript,
                round=state.round, user_note=pending_note,
            ):
                if ev.kind == "turn_end":
                    content, verdict = ev.content, ev.verdict
                yield ev
            transcript.append(Turn(critic.role, state.round, content, verdict=verdict))
            state.last_verdict = verdict

            # The note only emphasises the round it was given for; it stays in the
            # transcript for lasting context, but isn't re-flagged as priority.
            pending_note = ""

            if not state.should_continue():
                break

            # Another round will run (verdict REVISE, cap not reached): pause and
            # let the user steer it. `send(note)` resumes here; `next()` sends None.
            note = (
                yield Event(
                    "await_input", role=critic.role, round=state.round,
                    content=content, verdict=verdict,
                )
            ) or ""
            if note.strip():
                transcript.append(Turn("User", state.round, note))
                pending_note = note

        # Tell the UI why the loop ended, then document the outcome.
        reason = "Critic approved" if state.converged else f"reached the {self.max_rounds}-round cap"
        yield Event("status", text=f"Discussion complete ({reason}). Documenting the solution…")

        final = ""
        for ev in self._run_turn(
            summarizer, task=task, transcript=transcript,
            round=state.round, user_note=user_note,
        ):
            if ev.kind == "turn_end":
                final = ev.content
                yield Event("final", role=summarizer.role, content=final)
            else:
                yield ev
