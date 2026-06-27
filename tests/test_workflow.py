"""Verdict parsing and loop-state policy."""
from __future__ import annotations

from agentic_kris.orchestration.workflow import (
    APPROVE,
    REVISE,
    LoopState,
    parse_verdict,
)


def test_parse_verdict_approve():
    assert parse_verdict("blah\nVERDICT: APPROVE") == APPROVE


def test_parse_verdict_revise():
    assert parse_verdict("issues...\nVERDICT: REVISE please") == REVISE


def test_parse_verdict_defaults_to_revise():
    assert parse_verdict("no verdict here") == REVISE


def test_loop_stops_on_approve():
    s = LoopState(max_rounds=3, round=1, last_verdict=APPROVE)
    assert not s.should_continue()
    assert s.converged


def test_loop_continues_until_cap():
    s = LoopState(max_rounds=3)
    s.round, s.last_verdict = 1, REVISE
    assert s.should_continue()
    s.round = 3
    assert not s.should_continue()
    assert s.hit_cap
