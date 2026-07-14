"""fsutil.unlink_tolerant — the WinError 32 class fix (2026-07-14).

The 07-13 21:01 drift handoff died tracelessly: `daemon start` crashed
unlinking daemon-exit.txt while the serve status poll held it open.
These pin the helper's semantics and the lifecycle-path wiring.
"""
from __future__ import annotations

import inspect
from pathlib import Path

from Tooling.core import cli, dispatcher, fsutil


def test_unlink_existing(tmp_path):
    p = tmp_path / "f.txt"
    p.write_text("x")
    assert fsutil.unlink_tolerant(p) is True
    assert not p.exists()


def test_unlink_missing_is_ok(tmp_path):
    assert fsutil.unlink_tolerant(tmp_path / "absent.txt") is True


def test_unlink_persistent_lock_returns_false_no_raise(tmp_path,
                                                       monkeypatch):
    p = tmp_path / "held.txt"
    p.write_text("x")
    calls = {"n": 0}

    def always_locked(self, missing_ok=False):
        calls["n"] += 1
        raise PermissionError(32, "sharing violation")
    monkeypatch.setattr(Path, "unlink", always_locked)
    assert fsutil.unlink_tolerant(p, retries=3, delay_sec=0.0) is False
    assert calls["n"] == 3  # retried, never raised


def test_unlink_transient_lock_recovers(tmp_path, monkeypatch):
    p = tmp_path / "briefly-held.txt"
    p.write_text("x")
    real_unlink = Path.unlink
    calls = {"n": 0}

    def locked_once(self, missing_ok=False):
        calls["n"] += 1
        if calls["n"] == 1:
            raise PermissionError(32, "sharing violation")
        return real_unlink(self, missing_ok=missing_ok)
    monkeypatch.setattr(Path, "unlink", locked_once)
    assert fsutil.unlink_tolerant(p, retries=3, delay_sec=0.0) is True
    assert not p.exists()


# ------------------------------------------------------------- wiring pins

def test_daemon_start_clears_exit_summary_tolerantly():
    src = inspect.getsource(cli.daemon_start)
    assert 'fsutil.unlink_tolerant(logs / "daemon-exit.txt")' in src, (
        "the 21:01 crash site must use the tolerant unlink")
    assert '"daemon-exit.txt").unlink' not in src


def test_dispatcher_lifecycle_unlinks_are_tolerant():
    src = inspect.getsource(dispatcher.run)
    assert "fsutil.unlink_tolerant" in src
    # No bare unlink on the lifecycle files inside run() — the pid-lock
    # atexit and the stop/starting files all go through the helper.
    assert ".unlink(missing_ok=True)" not in src


def test_cli_robust_unlink_delegates():
    src = inspect.getsource(cli._robust_unlink)
    assert "fsutil.unlink_tolerant" in src
