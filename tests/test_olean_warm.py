"""`PromotionGate` worker contract (was the #103 `OleanWarmer`; owner
ruling 2026-08-30, task #231: the background build is the promotion's
cold-build GATE, and its verdict — not a log line — is what housekeeping
acts on). The name `OleanWarmer` stays as an alias.

Per-promotion semantics live in `test_promotion_gate.py`; this file
pins the worker itself: one build per strategy id, distinct ids each
build, a disabled gate answers at once, an exception is a FAILURE
result (never swallowed).
"""
from __future__ import annotations

import threading
from pathlib import Path

import pytest

from Tooling.pipeline import _lake
from Tooling.pipeline._olean_warm import OleanWarmer, PromotionGate


@pytest.fixture
def calls(monkeypatch):
    seen: list[list[str]] = []
    gate_evt = threading.Event()

    def fake_build(ws, mods):
        seen.append(list(mods))
        gate_evt.wait(timeout=2)
        return True, "ok"
    monkeypatch.setattr(_lake, "lake_build_modules", fake_build)
    return seen, gate_evt


def test_alias_name_is_the_gate():
    assert OleanWarmer is PromotionGate


def test_submit_builds_and_answers(tmp_path, calls):
    seen, evt = calls
    g = PromotionGate(tmp_path, enabled=True)
    try:
        g.submit(1, ["Problems.p.proofs.L_a"])
        evt.set()
        r = g.wait_result(1, timeout=5)
        assert r is not None and r.ok is True
        assert seen == [["Problems.p.proofs.L_a"]]
    finally:
        g.shutdown(wait=True)


def test_disabled_gate_answers_built_at_once(tmp_path, calls):
    seen, _ = calls
    g = PromotionGate(tmp_path, enabled=False)
    g.submit(1, ["Problems.p.proofs.L_a"])
    assert not g.pending(1) or g.drain_results()
    res = g.drain_results() or []
    assert seen == [], "disabled: nothing is built"
    assert not g.has_pending()


def test_same_strategy_is_built_once_while_pending(tmp_path, calls):
    seen, evt = calls
    g = PromotionGate(tmp_path, enabled=True)
    try:
        g.submit(7, ["Problems.p.proofs.L_a"])
        g.submit(7, ["Problems.p.proofs.L_a"])
        g.submit(7, ["Problems.p.proofs.L_a", "Problems.p.proofs._strategy_x"])
        evt.set()
        assert g.wait_result(7, timeout=5) is not None
        assert len(seen) == 1
    finally:
        g.shutdown(wait=True)


def test_distinct_strategies_both_build(tmp_path, calls):
    seen, evt = calls
    g = PromotionGate(tmp_path, enabled=True)
    try:
        g.submit(1, ["Problems.p.proofs.L_a"])
        g.submit(2, ["Problems.p.proofs.L_b"])
        evt.set()
        assert g.wait_result(1, timeout=5).ok and g.wait_result(2, timeout=5).ok
        assert sorted(m[0] for m in seen) == ["Problems.p.proofs.L_a",
                                               "Problems.p.proofs.L_b"]
    finally:
        g.shutdown(wait=True)


def test_build_exception_is_a_failure_result_not_swallowed(tmp_path, monkeypatch):
    from Tooling.core import degraded

    def boom(ws, mods):
        raise RuntimeError("lake exploded")
    monkeypatch.setattr(_lake, "lake_build_modules", boom)
    recorded = []
    monkeypatch.setattr(degraded, "record",
                        lambda ws, kind, detail="": recorded.append(kind))
    g = PromotionGate(tmp_path, enabled=True)
    try:
        g.submit(3, ["Problems.p.proofs.L_a"])
        r = g.wait_result(3, timeout=5)
        assert r is not None and r.ok is False
        assert "lake exploded" in r.detail
        assert recorded == ["promotion_build"]
    finally:
        g.shutdown(wait=True)
