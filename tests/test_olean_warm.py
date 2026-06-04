"""Background .olean warmer (#103).

OleanWarmer runs a cold `lake build` of a just-promoted alias module on
its own daemon thread, so the root integrity probe finds the spine warm.
These tests mock `lake_build` (no real lake invocation) and use an Event
to synchronise with the warmer's worker thread.
"""
from __future__ import annotations

import threading
from pathlib import Path

from Tooling.pipeline import _olean_warm
from Tooling.pipeline._olean_warm import OleanWarmer


def _install_recorder(monkeypatch, *, raise_on=None):
    """Replace lake_build with a recorder. Returns (calls, done_event).
    `raise_on`: a substring; if a target path contains it, the fake build
    raises (to exercise best-effort error handling)."""
    calls: list[Path] = []
    done = threading.Event()

    def fake_lake_build(workspace: Path, target_lean: Path):
        calls.append(target_lean)
        done.set()
        if raise_on and raise_on in str(target_lean):
            raise RuntimeError("boom")
        return True, ""

    monkeypatch.setattr(_olean_warm, "lake_build", fake_lake_build)
    return calls, done


def test_submit_triggers_build(monkeypatch, tmp_path):
    calls, done = _install_recorder(monkeypatch)
    w = OleanWarmer(tmp_path, enabled=True)
    try:
        target = tmp_path / "Problems" / "p" / "X.lean"
        w.submit(target)
        assert done.wait(timeout=5.0), "worker never ran lake_build"
        assert calls == [target]
    finally:
        w.shutdown(wait=True)


def test_disabled_is_noop(monkeypatch, tmp_path):
    calls, done = _install_recorder(monkeypatch)
    w = OleanWarmer(tmp_path, enabled=False)
    w.submit(tmp_path / "Problems" / "p" / "X.lean")
    # No worker thread exists; nothing should run.
    assert not done.wait(timeout=0.3)
    assert calls == []
    w.shutdown(wait=True)  # idempotent / safe on disabled


def test_dedup_same_module_not_rebuilt(monkeypatch, tmp_path):
    """A module already queued/building is not re-enqueued. We gate the
    fake build on a release Event so both submits land while the first is
    still in-flight, then assert only one build ran."""
    release = threading.Event()
    calls: list[Path] = []
    first_started = threading.Event()

    def fake_lake_build(workspace: Path, target_lean: Path):
        calls.append(target_lean)
        first_started.set()
        release.wait(timeout=5.0)
        return True, ""

    monkeypatch.setattr(_olean_warm, "lake_build", fake_lake_build)
    w = OleanWarmer(tmp_path, enabled=True)
    try:
        target = tmp_path / "Problems" / "p" / "X.lean"
        w.submit(target)
        assert first_started.wait(timeout=5.0)
        w.submit(target)          # dedup: in-flight module
        release.set()
        w.shutdown(wait=True)
        assert calls == [target], f"expected 1 build, got {calls}"
    finally:
        release.set()


def test_distinct_modules_both_build(monkeypatch, tmp_path):
    calls, _done = _install_recorder(monkeypatch)
    seen = threading.Event()
    lock = threading.Lock()

    def fake_lake_build(workspace: Path, target_lean: Path):
        with lock:
            calls.append(target_lean)
            if len(calls) >= 2:
                seen.set()
        return True, ""

    monkeypatch.setattr(_olean_warm, "lake_build", fake_lake_build)
    w = OleanWarmer(tmp_path, enabled=True)
    try:
        a = tmp_path / "Problems" / "p" / "A.lean"
        b = tmp_path / "Problems" / "p" / "B.lean"
        w.submit(a)
        w.submit(b)
        assert seen.wait(timeout=5.0)
        assert set(calls) == {a, b}
    finally:
        w.shutdown(wait=True)


def test_build_exception_is_swallowed(monkeypatch, tmp_path):
    """A raising lake_build must not kill the worker thread — a later
    submit on a different module still runs."""
    good_ran = threading.Event()

    def fake(workspace, target_lean):
        if "Bad" in str(target_lean):
            raise RuntimeError("boom")
        good_ran.set()
        return True, ""

    monkeypatch.setattr(_olean_warm, "lake_build", fake)
    w = OleanWarmer(tmp_path, enabled=True)
    try:
        w.submit(tmp_path / "Bad.lean")
        w.submit(tmp_path / "Good.lean")
        assert good_ran.wait(timeout=5.0), "worker died on exception"
    finally:
        w.shutdown(wait=True)
