"""Loop policy for the research<->critique workflow.

Factored out of the supervisor so the convergence rules (verdict parsing, round
cap) are easy to test and so alternative workflows can reuse or replace them
without touching agent code.
"""
from __future__ import annotations

from dataclasses import dataclass

APPROVE = "APPROVE"
REVISE = "REVISE"


def parse_verdict(text: str) -> str:
    """Extract the Critic's verdict from its message.

    Looks for the last ``VERDICT`` marker; defaults to REVISE (another round)
    when the verdict is missing or ambiguous, so the loop errs toward more
    scrutiny rather than less.
    """
    upper = text.upper()
    idx = upper.rfind("VERDICT")
    if idx != -1:
        tail = upper[idx:]
        if APPROVE in tail:
            return APPROVE
        if REVISE in tail:
            return REVISE
    return REVISE


@dataclass
class LoopState:
    """Tracks progress of the Researcher<->Critic loop."""

    max_rounds: int
    round: int = 0
    last_verdict: str = ""

    def should_continue(self) -> bool:
        """True if another Researcher->Critic round should run."""
        if self.last_verdict == APPROVE:
            return False
        return self.round < self.max_rounds

    @property
    def converged(self) -> bool:
        return self.last_verdict == APPROVE

    @property
    def hit_cap(self) -> bool:
        return self.round >= self.max_rounds and self.last_verdict != APPROVE
