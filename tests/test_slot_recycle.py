"""Slot recycling: the third memory mechanism, and why it is separate.

The gateway already had two. Neither could do this one's job:

  job cap (8 GB)   how much ONE elaboration may commit before the OS
                   kills it. Hard, fatal, and it fires while Lean is
                   busy.
  wedge watchdog   restarts the backend when an elaborate hangs past
                   600s. By construction it only ever fires while Lean
                   is busy — measured 2026-08-14: 683 h of gateway
                   lifetime, 28 restarts, every one triggered by a
                   stuck elaboration.

Recycling asks a question neither of those asks: how fat may a slot get
ACROSS elaborations before starting it over is cheaper than keeping it.
Measured on union_closed the same day: baseline 0.65-0.8 GB, and one
claimed slot serving the `decide`-heavy 634 family reached 2.58 GB in
~36 minutes and then sat flat while its four siblings stayed at
baseline.
"""
from __future__ import annotations

import sys
import types

import pytest


@pytest.fixture
def gw(monkeypatch):
    from Tooling.lsp import gateway
    return gateway


def _slot(gateway, slot_id=0, uri="file:///s0.lean", claimed=None):
    import threading
    from pathlib import Path
    s = gateway.WorkerSlot(slot_id=slot_id, slot_path=Path("s0.lean"),
                           slot_uri=uri)
    s.lock = threading.Lock()
    s.claimed_by = claimed
    return s


def test_the_threshold_sits_between_the_baseline_and_the_fat_slot(gw):
    """Both bounds are measurements, not taste: 0.8 GB was the heaviest
    healthy slot and 2.58 GB the observed fat one, so the knob has to
    separate them with room on each side."""
    assert 800 < gw.SLOT_RECYCLE_MB_DEFAULT < 2580


def test_the_recycle_knob_is_far_below_the_job_cap():
    """They answer different questions and must not be collapsed into
    one number. If someone ever tunes them together, this is where the
    two clocks stop matching — which is the 900s/780s lesson, in RAM."""
    from Tooling.core import config as cfg
    from Tooling.lsp import gateway
    job_cap = int(cfg.get("gateway.lean_memory_cap_mb", default=8192,
                          cast=int))
    assert gateway.SLOT_RECYCLE_MB_DEFAULT * 2 < job_cap


def test_a_claimed_slot_is_never_recycled(gw, monkeypatch, capsys):
    """The 2026-08-13 slot-handback incident in the other direction: a
    slot taken from a live owner costs that pipeline its next tool call
    and the goal an attempt."""
    called: list = []
    monkeypatch.setattr(gw, "_slot_private_mb", lambda: {0: 9999})
    monkeypatch.setattr(gw._state, "backend",
                        types.SimpleNamespace(
                            did_close=lambda *_a: called.append("close"),
                            did_open=lambda *_a: called.append("open"),
                            wait_for_file_done=lambda *_a, **_k: None))
    monkeypatch.setattr(gw._state, "workers", [])
    gw._recycle_slot_if_heavy(_slot(gw, claimed="pipeline-7"))
    assert called == [], "recycled a slot somebody was holding"


def test_a_busy_slot_is_never_recycled(gw, monkeypatch):
    called: list = []
    monkeypatch.setattr(gw, "_slot_private_mb", lambda: {0: 9999})
    monkeypatch.setattr(gw._state, "backend",
                        types.SimpleNamespace(
                            did_close=lambda *_a: called.append("close"),
                            did_open=lambda *_a: called.append("open"),
                            wait_for_file_done=lambda *_a, **_k: None))
    s = _slot(gw)
    s.lock.acquire()                     # somebody is elaborating on it
    try:
        gw._recycle_slot_if_heavy(s)
    finally:
        s.lock.release()
    assert called == []


def test_a_slot_under_the_threshold_is_left_alone(gw, monkeypatch):
    called: list = []
    monkeypatch.setattr(gw, "_slot_private_mb", lambda: {0: 700})
    monkeypatch.setattr(gw._state, "backend",
                        types.SimpleNamespace(
                            did_close=lambda *_a: called.append("close"),
                            did_open=lambda *_a: called.append("open"),
                            wait_for_file_done=lambda *_a, **_k: None))
    gw._recycle_slot_if_heavy(_slot(gw))
    assert called == []


def test_an_unmeasured_slot_is_left_alone(gw, monkeypatch):
    """None is "could not measure", not "zero" and not "huge". Acting on
    a reading nobody took is how a healthy slot gets restarted."""
    called: list = []
    monkeypatch.setattr(gw, "_slot_private_mb", lambda: {0: None})
    monkeypatch.setattr(gw._state, "backend",
                        types.SimpleNamespace(
                            did_close=lambda *_a: called.append("close"),
                            did_open=lambda *_a: called.append("open"),
                            wait_for_file_done=lambda *_a, **_k: None))
    gw._recycle_slot_if_heavy(_slot(gw))
    assert called == []


def test_a_fat_idle_slot_is_closed_and_reopened(gw, monkeypatch, capsys):
    """The close is the point. `did_change_full` swaps content and keeps
    the process, so it cannot return the heap — which is why this needed
    a verb the client did not have."""
    called: list = []
    monkeypatch.setattr(gw, "_slot_private_mb", lambda: {0: 2600})
    monkeypatch.setattr(gw._state, "backend",
                        types.SimpleNamespace(
                            did_close=lambda *_a: called.append("close"),
                            did_open=lambda *_a: called.append("open"),
                            wait_for_file_done=lambda *_a, **_k: None))
    gw._recycle_slot_if_heavy(_slot(gw))
    assert called == ["close", "open"]
    assert "recycling" in capsys.readouterr().err


def test_a_failed_recycle_still_leaves_the_slot_open(gw, monkeypatch,
                                                    capsys):
    """A half-finished recycle would take a worker out of the pool for
    the rest of the run — worse than any amount of memory. The re-open
    is retried on the error path and the failure is printed, not
    raised."""
    called: list = []

    def _boom(*_a, **_k):
        raise RuntimeError("backend went away mid-recycle")

    monkeypatch.setattr(gw, "_slot_private_mb", lambda: {0: 2600})
    monkeypatch.setattr(gw._state, "backend",
                        types.SimpleNamespace(
                            did_close=lambda *_a: called.append("close"),
                            did_open=lambda *_a: called.append("open"),
                            wait_for_file_done=_boom))
    gw._recycle_slot_if_heavy(_slot(gw))          # must not raise
    assert called.count("open") == 2, called
    assert "recycle FAILED" in capsys.readouterr().err


def test_recycle_waits_for_the_worker_death_between_close_and_open(
        gw, monkeypatch):
    """didClose is a notification — a didOpen that lands before the old
    worker dies makes the server keep the same process and heap. 308 of
    315 historical recycles were exactly that no-op ("recycled in 0.0s —
    5831 MB -> 5831 MB", 2026-08-26): the wait IS the fix."""
    called: list = []
    monkeypatch.setattr(gw, "_slot_private_mb", lambda: {0: 2600})
    monkeypatch.setattr(gw, "_await_worker_exit",
                        lambda *_a, **_k: called.append("await") or True)
    monkeypatch.setattr(gw._state, "backend",
                        types.SimpleNamespace(
                            did_close=lambda *_a: called.append("close"),
                            did_open=lambda *_a: called.append("open"),
                            wait_for_file_done=lambda *_a, **_k: None))
    gw._recycle_slot_if_heavy(_slot(gw))
    assert called[:3] == ["close", "await", "open"]


def test_a_surviving_worker_is_hard_killed_never_reattached(
        gw, monkeypatch, capsys):
    """A reattach would keep the old heap and log a recycle that never
    happened. The escalation is the wedge path's proven kill."""
    called: list = []
    monkeypatch.setattr(gw, "_slot_private_mb", lambda: {0: 2600})
    monkeypatch.setattr(gw, "_await_worker_exit", lambda *_a, **_k: False)
    monkeypatch.setattr(gw, "_kill_worker_for_uri",
                        lambda *_a: called.append("kill") or True)
    monkeypatch.setattr(gw._state, "backend",
                        types.SimpleNamespace(
                            did_close=lambda *_a: called.append("close"),
                            did_open=lambda *_a: called.append("open"),
                            wait_for_file_done=lambda *_a, **_k: None))
    gw._recycle_slot_if_heavy(_slot(gw))
    assert called[:3] == ["close", "kill", "open"]
    assert "hard-killed" in capsys.readouterr().err


def test_await_worker_exit_semantics(gw, monkeypatch):
    """No worker found -> gone (True, fast). A live process -> False
    once the wait expires (the caller escalates)."""
    monkeypatch.setattr(gw, "_worker_pid_for_uri", lambda _u: None)
    assert gw._await_worker_exit("file:///s0.lean", timeout=0.2) is True
    import os as _os
    monkeypatch.setattr(gw, "_worker_pid_for_uri",
                        lambda _u: _os.getpid())   # provably alive
    assert gw._await_worker_exit("file:///s0.lean", timeout=0.4) is False


def test_midlease_threshold_targets_residue_not_live_sets(gw, monkeypatch):
    """3x the recycle line: the heaviest measured single-content live
    set is ~2.2 GB, so restarting below ~4.5 GB rebuilds what it just
    freed. Env override is absolute."""
    monkeypatch.delenv("ASTERISM_MIDLEASE_REWARM_MB", raising=False)
    assert gw._midlease_rewarm_mb() == int(
        gw.SLOT_RECYCLE_MB_DEFAULT * gw._MIDLEASE_REWARM_FACTOR)
    monkeypatch.setenv("ASTERISM_MIDLEASE_REWARM_MB", "6000")
    assert gw._midlease_rewarm_mb() == 6000


def test_midlease_kick_guards(gw, monkeypatch):
    """No probe metas, no cooldown violations, no double-flight — and a
    fat idle slot after a tool return DOES kick the background
    thread."""
    import time as _time
    started: list = []
    monkeypatch.setattr(gw.threading, "Thread",
                        lambda **kw: types.SimpleNamespace(
                            start=lambda: started.append(kw["name"])))
    monkeypatch.setattr(gw, "_slot_private_mb_cached", lambda: {0: 9999})
    monkeypatch.setattr(gw._state, "backend", object())
    meta = types.SimpleNamespace(pipeline_id="p1")
    s = _slot(gw, claimed="p1")
    gw._maybe_kick_midlease_rewarm(s, None)          # borrow: never
    assert not started
    s.rewarming = True
    gw._maybe_kick_midlease_rewarm(s, meta)          # single-flight
    assert not started
    s.rewarming = False
    s.rewarmed_at = _time.monotonic()
    gw._maybe_kick_midlease_rewarm(s, meta)          # cooldown
    assert not started
    s.rewarmed_at = 0.0
    monkeypatch.setattr(gw, "_slot_private_mb_cached", lambda: {0: 900})
    gw._maybe_kick_midlease_rewarm(s, meta)          # thin: no
    assert not started and s.rewarming is False
    monkeypatch.setattr(gw, "_slot_private_mb_cached", lambda: {0: 9999})
    gw._maybe_kick_midlease_rewarm(s, meta)          # fat idle: KICK
    assert started and s.rewarming is True


def test_midlease_rewarm_restores_content_after_a_real_death(
        gw, monkeypatch, capsys):
    """Order is the contract: content computed BEFORE the close (a
    failure must leave the old worker running), then close -> await
    death (hard kill on survival) -> fresh didOpen with the session's
    merged unit."""
    called: list = []
    meta = types.SimpleNamespace(pipeline_id="p1")
    monkeypatch.setattr(gw, "_compilation_for",
                        lambda m: (called.append("content") or
                                   ("MERGED", [None, 1])))
    monkeypatch.setattr(gw, "_await_worker_exit",
                        lambda *_a, **_k: called.append("await") or False)
    monkeypatch.setattr(gw, "_kill_worker_for_uri",
                        lambda *_a: called.append("kill") or True)
    monkeypatch.setattr(gw, "_slot_private_mb", lambda: {0: 500})
    monkeypatch.setattr(gw._state, "backend",
                        types.SimpleNamespace(
                            did_close=lambda *_a: called.append("close"),
                            did_open=lambda _p, txt: called.append(
                                ("open", txt)),
                            wait_for_file_done=lambda *_a, **_k: None))
    s = _slot(gw, claimed="p1")
    s.rewarming = True
    import tempfile
    from pathlib import Path
    s.slot_path = Path(tempfile.mkdtemp()) / "s0.lean"
    gw._midlease_rewarm_run(s, meta, 9999)
    assert called == ["content", "close", "await", "kill",
                      ("open", "MERGED")]
    assert s.content_pipeline_id == "p1" and s.rewarming is False
    assert "mid-lease rewarm" in capsys.readouterr().err


def test_midlease_rewarm_failure_reopens_warmup_never_bricks(
        gw, monkeypatch, capsys):
    opens: list = []
    meta = types.SimpleNamespace(pipeline_id="p1")
    monkeypatch.setattr(gw, "_compilation_for",
                        lambda m: ("MERGED", [None]))
    monkeypatch.setattr(gw, "_await_worker_exit", lambda *_a, **_k: True)
    monkeypatch.setattr(gw, "_slot_private_mb", lambda: {0: 500})

    def open_boom(_p, txt):
        opens.append(txt)
        if txt == "MERGED":
            raise RuntimeError("elab node fell over")

    monkeypatch.setattr(gw._state, "backend",
                        types.SimpleNamespace(
                            did_close=lambda *_a: None,
                            did_open=open_boom,
                            wait_for_file_done=lambda *_a, **_k: None))
    s = _slot(gw, claimed="p1")
    s.rewarming = True
    import tempfile
    from pathlib import Path
    s.slot_path = Path(tempfile.mkdtemp()) / "s0.lean"
    gw._midlease_rewarm_run(s, meta, 9999)          # must not raise
    assert opens == ["MERGED", gw.WARMUP_CONTENT]
    assert s.content_pipeline_id is None and s.rewarming is False
    assert "FAILED" in capsys.readouterr().err


def test_acquire_slides_and_credits_while_rewarming(gw):
    """The blocked caller's wait is the framework's, not the agent's —
    same contract as the elab gate (source pin: the acquire loop must
    slide its deadline on `rewarming` and record the credit)."""
    import inspect
    src = inspect.getsource(gw._acquire_slot)
    assert "rewarming" in src and "_record_queue_credit" in src
    assert "_maybe_kick_midlease_rewarm" in src


def test_the_reading_is_private_bytes_not_working_set():
    """Working set counts the shared mathlib mmap once per process:
    measured 2026-08-14, five workers reported 17.93 GB of working set
    against 5.38 GB private on a box using 11.5 GB. A reading taken the
    other way would recycle every slot, forever."""
    import inspect
    from Tooling.lsp import gateway
    src = inspect.getsource(gateway._slot_private_mb)
    assert "private" in src and "uss" in src
    assert "rss" not in src.lower().split("never rss")[-1][:400]


@pytest.mark.skipif(sys.platform != "win32",
                    reason="cmdline shape measured on the Windows pool")
def test_the_slot_to_worker_map_reads_the_workers_own_argv():
    """Not process order, not counting: Lean puts the document URI on
    its worker's command line, so the mapping is exact and survives
    restarts in any order."""
    import inspect
    from Tooling.lsp import gateway
    src = inspect.getsource(gateway._slot_private_mb)
    assert "--worker" in src and "cmdline" in src
