"""The freeze mechanism (owner design 2026-08-26): over the RAM
budget, the fattest idle worker is KILLED but its session and claim
survive; tool calls queue on the slot with wall credit; the thaw
rebuilds the worker from the session's own content when pressure
clears. A suspend, not a kill — the answer to the fleet-level blind
spot both 08-26 crush post-mortems named (pausing dispatch stops
reinforcements, nothing stopped the in-flight fleet's collective
inflation; the kernel's own relief at the MemoryMax line is a
strangle, not a kill)."""
from __future__ import annotations

import threading
import types
from pathlib import Path

import pytest


@pytest.fixture
def gw(monkeypatch):
    from Tooling.lsp import gateway
    monkeypatch.setattr(gateway._state, "first_warm_done", True)
    monkeypatch.setattr(gateway._state, "ram_budget_gb", 20.0)
    monkeypatch.setattr(gateway.governor, "_await_worker_exit",
                        lambda *_a, **_k: True)
    monkeypatch.setattr(gateway.governor, "_kill_worker_for_uri",
                        lambda *_a: True)
    return gateway


def _slot(gw, slot_id=0, claimed="p1"):
    s = gw.WorkerSlot(slot_id=slot_id,
                      slot_path=Path(f"s{slot_id}.lean"),
                      slot_uri=f"file:///s{slot_id}.lean")
    s.lock = threading.Lock()
    s.claimed_by = claimed
    return s


def _backend(gw, monkeypatch, calls):
    monkeypatch.setattr(gw._state, "backend", types.SimpleNamespace(
        did_close=lambda *_a: calls.append("close"),
        did_open=lambda _p, txt: calls.append(("open", txt)),
        wait_for_file_done=lambda *_a, **_k: None))


def test_over_budget_freezes_the_fattest_idle_and_keeps_the_claim(
        gw, monkeypatch, capsys):
    calls: list = []
    _backend(gw, monkeypatch, calls)
    from Tooling.core import ram_ledger as rl
    monkeypatch.setattr(rl, "framework_current_gb", lambda: 22.0)
    fat, thin = _slot(gw, 0, "p1"), _slot(gw, 1, "p2")
    monkeypatch.setattr(gw._state, "workers", [thin, fat])
    monkeypatch.setattr(gw.governor, "_slot_private_mb_cached",
                        lambda: {0: 5000, 1: 700})
    assert gw._freeze_tick() == 1
    assert fat.frozen is True and fat.claimed_by == "p1", \
        "the worker dies, the session's claim survives"
    assert thin.frozen is False
    assert "close" in calls
    assert "FROZEN" in capsys.readouterr().err


def test_freeze_never_takes_the_last_worker(gw, monkeypatch):
    calls: list = []
    _backend(gw, monkeypatch, calls)
    from Tooling.core import ram_ledger as rl
    monkeypatch.setattr(rl, "framework_current_gb", lambda: 30.0)
    only = _slot(gw, 0, "p1")
    monkeypatch.setattr(gw._state, "workers", [only])
    monkeypatch.setattr(gw.governor, "_slot_private_mb_cached",
                        lambda: {0: 9000})
    assert gw._freeze_tick() == 0
    assert only.frozen is False


def test_busy_slots_freeze_only_under_deep_overshoot(gw, monkeypatch):
    calls: list = []
    _backend(gw, monkeypatch, calls)
    from Tooling.core import ram_ledger as rl
    cur = {"v": 21.0}
    monkeypatch.setattr(rl, "framework_current_gb", lambda: cur["v"])
    busy1, busy2, thin = (_slot(gw, 0, "p1"), _slot(gw, 1, "p2"),
                          _slot(gw, 2, "p3"))
    busy1.lock.acquire()         # mid-elaboration
    busy2.lock.acquire()
    monkeypatch.setattr(gw._state, "workers", [busy1, busy2, thin])
    monkeypatch.setattr(gw.governor, "_slot_private_mb_cached",
                        lambda: {0: 9000, 1: 8000, 2: 500})
    try:
        gw._freeze_tick()        # overshoot 1G: only the idle may go
        assert busy1.frozen is False and busy2.frozen is False, \
            "shallow overshoot must not kill mid-elaboration"
        cur["v"] = 20.0 + gw.governor._FREEZE_BUSY_ESCALATION_GB + 6.0
        gw._freeze_tick()
        assert busy1.frozen is True, \
            "deep overshoot escalates to the fattest busy worker"
    finally:
        busy1.lock.release()
        busy2.lock.release()


def test_thaw_reopens_warmup_and_leaves_the_content_to_the_owner(
        gw, monkeypatch, capsys, tmp_path):
    """Owner ruling 2026-08-29: the thaw returns a slot, not a proof
    state. Restoring the session's content inside the thaw queued on the
    elaboration lanes (600s on the 4-OCPU flagship) and failed with a
    message the agent could not act on; now it is a ~1s warmup reopen
    that needs no lane, and the owner's next call swaps its content in
    under the gate with queue credit, like any cold claim."""
    calls: list = []
    _backend(gw, monkeypatch, calls)
    from Tooling.core import ram_ledger as rl
    monkeypatch.setattr(rl, "framework_current_gb", lambda: 10.0)
    monkeypatch.setattr(gw.governor, "_compilation_for",
                        lambda m: (_ for _ in ()).throw(AssertionError(
                            "thaw must not rebuild the session's content")))
    s = _slot(gw, 0, "p1")
    s.frozen, s.frozen_at = True, 0.0
    s.slot_path = tmp_path / "s0.lean"
    meta = types.SimpleNamespace(pipeline_id="p1")
    monkeypatch.setattr(gw._state, "workers", [s])
    monkeypatch.setattr(gw._state, "sessions", {"tok": meta})
    assert gw._freeze_tick() == 1
    assert s.frozen is False
    assert ("open", gw.WARMUP_CONTENT) in calls
    assert s.content_pipeline_id is None, "the owner reloads on its next call"
    assert "THAWED to warmup" in capsys.readouterr().err


def test_thaw_of_a_released_session_reopens_warmup(gw, monkeypatch,
                                                   tmp_path):
    calls: list = []
    _backend(gw, monkeypatch, calls)
    from Tooling.core import ram_ledger as rl
    monkeypatch.setattr(rl, "framework_current_gb", lambda: 10.0)
    s = _slot(gw, 0, claimed=None)
    s.frozen = True
    s.slot_path = tmp_path / "s0.lean"
    monkeypatch.setattr(gw._state, "workers", [s])
    monkeypatch.setattr(gw._state, "sessions", {})
    gw._freeze_tick()
    assert s.frozen is False and s.content_pipeline_id is None
    assert ("open", gw.WARMUP_CONTENT) in calls


