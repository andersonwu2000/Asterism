"""Oracle ARM64 readiness P0#5 — zen shim service control on POSIX.

Before this fix `zen_shim`'s detached-service commands (`start` / `stop`
/ `status`) were Windows-only: `_pid_alive` shelled out to `tasklist`,
`_svc_stop` to `taskkill`, and `_svc_start`'s detach flags
(`DETACHED_PROCESS` / `CREATE_NEW_PROCESS_GROUP`) are no-ops off
Windows (`getattr(subprocess, ..., 0)` silently returns 0), so a POSIX
`start` launched a child that shared the launching shell's session and
died with it on SIGHUP the moment that shell exited — exactly the
failure the detached form exists to avoid (see the module comment
above `_PID_FILE`).

Runs on Windows CI (repo convention): the POSIX branch is reached by
monkeypatching `os.name` plus the POSIX-only `os` entry points
(`kill`) that exist on Windows only with different semantics, so tests
fake them out entirely rather than touching a real process.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from Tooling.llm import zen_shim


# ---------------------------------------------------------------------
# _pid_alive_posix / _proc_cmdline_mentions
# ---------------------------------------------------------------------

def test_pid_alive_posix_true_on_esrch_free_probe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(zen_shim.os, "kill", lambda pid, sig: None,
                        raising=False)
    monkeypatch.setattr(zen_shim, "_proc_cmdline_mentions",
                        lambda pid, needle: True)
    assert zen_shim._pid_alive_posix(4242) is True


def test_pid_alive_posix_false_on_esrch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _raise(pid, sig):
        raise ProcessLookupError()
    monkeypatch.setattr(zen_shim.os, "kill", _raise, raising=False)
    assert zen_shim._pid_alive_posix(4242) is False


def test_pid_alive_posix_true_on_eperm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """EPERM means the pid exists and is owned by someone else — still
    a live pid, which is all liveness asks."""
    def _raise(pid, sig):
        raise PermissionError()
    monkeypatch.setattr(zen_shim.os, "kill", _raise, raising=False)
    assert zen_shim._pid_alive_posix(4242) is True


def test_pid_alive_posix_rejects_a_reused_pid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The pid answers to signal 0 (something is running there) but
    `/proc/<pid>/cmdline` doesn't mention the shim — a different
    process now owns this pid, and the identity guard must say so."""
    monkeypatch.setattr(zen_shim.os, "kill", lambda pid, sig: None,
                        raising=False)
    monkeypatch.setattr(zen_shim, "_proc_cmdline_mentions",
                        lambda pid, needle: False)
    assert zen_shim._pid_alive_posix(4242) is False


def test_cmdline_mentions_reads_proc(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import io

    def _fake_open(path, mode="r", *a, **kw):
        assert path == "/proc/4242/cmdline"
        assert mode == "rb"
        return io.BytesIO(b"python\x00-m\x00Tooling.llm.zen_shim\x008898\x00")

    monkeypatch.setattr("builtins.open", _fake_open)
    assert zen_shim._proc_cmdline_mentions(4242, "zen_shim") is True


def test_cmdline_mentions_false_for_unrelated_process(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import io

    def _fake_open(path, mode="r", *a, **kw):
        return io.BytesIO(b"some-other-daemon\x00--flag\x00")

    monkeypatch.setattr("builtins.open", _fake_open)
    assert zen_shim._proc_cmdline_mentions(4242, "zen_shim") is False


def test_cmdline_mentions_true_when_unreadable() -> None:
    """No /proc on this host (not Linux) — this test runs unmodified
    for real, no monkeypatch: 'unknown' must not read as 'dead'."""
    assert zen_shim._proc_cmdline_mentions(1, "zen_shim") is True


def test_pid_alive_dispatches_by_os_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(zen_shim.os, "name", "posix")
    monkeypatch.setattr(zen_shim, "_pid_alive_posix", lambda pid: "posix!")
    assert zen_shim._pid_alive(4242) == "posix!"


# ---------------------------------------------------------------------
# _kill_pid_posix — SIGTERM, bounded grace, SIGKILL
# ---------------------------------------------------------------------

def test_kill_pid_posix_term_then_grace_then_kill(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list = []
    monkeypatch.setattr(zen_shim.os, "kill",
                        lambda pid, sig: calls.append((pid, sig)),
                        raising=False)
    monkeypatch.setattr(zen_shim, "_pid_alive_posix", lambda pid: True)
    zen_shim._kill_pid_posix(4242, grace_sec=0.0)
    assert calls == [(4242, zen_shim.signal.SIGTERM),
                      (4242, zen_shim._SIGKILL)]


def test_kill_pid_posix_skips_sigkill_once_dead(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list = []
    monkeypatch.setattr(zen_shim.os, "kill",
                        lambda pid, sig: calls.append((pid, sig)),
                        raising=False)
    monkeypatch.setattr(zen_shim, "_pid_alive_posix", lambda pid: False)
    zen_shim._kill_pid_posix(4242, grace_sec=5.0)
    assert calls == [(4242, zen_shim.signal.SIGTERM)]


def test_kill_pid_posix_never_raises_on_already_gone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _raise(pid, sig):
        raise ProcessLookupError()
    monkeypatch.setattr(zen_shim.os, "kill", _raise, raising=False)
    zen_shim._kill_pid_posix(4242)  # must not raise


# ---------------------------------------------------------------------
# _detach_popen_kwargs — platform dispatch
# ---------------------------------------------------------------------

def test_detach_kwargs_posix_uses_start_new_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(zen_shim.os, "name", "posix")
    assert zen_shim._detach_popen_kwargs() == {"start_new_session": True}


def test_detach_kwargs_windows_uses_creationflags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(zen_shim.os, "name", "nt")
    kwargs = zen_shim._detach_popen_kwargs()
    assert "creationflags" in kwargs
    assert "start_new_session" not in kwargs


# ---------------------------------------------------------------------
# _svc_stop — routes through the POSIX kill on POSIX, taskkill on
# Windows, and always clears the pid file
# ---------------------------------------------------------------------

def test_svc_stop_posix_routes_through_kill_pid_posix(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    pid_file = tmp_path / "zen_shim.pid"
    pid_file.write_text("4242", encoding="ascii")
    monkeypatch.setattr(zen_shim, "_PID_FILE", str(pid_file))
    monkeypatch.setattr(zen_shim, "_svc_status", lambda port: (4242, True))
    called: list = []
    monkeypatch.setattr(zen_shim, "_kill_pid_posix",
                        lambda pid, **kw: called.append(pid))
    monkeypatch.setattr(zen_shim.os, "name", "posix")
    assert zen_shim._svc_stop(8898) == 0
    assert called == [4242]
    assert not pid_file.exists()


def test_svc_stop_never_kills_when_no_identified_pid(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """`_svc_status` returning `pid=None` means the identity/liveness
    check already failed (dead, or a reused pid that isn't the shim) —
    `_svc_stop` must not attempt to kill anything, on either platform."""
    pid_file = tmp_path / "zen_shim.pid"
    pid_file.write_text("4242", encoding="ascii")
    monkeypatch.setattr(zen_shim, "_PID_FILE", str(pid_file))
    monkeypatch.setattr(zen_shim, "_svc_status", lambda port: (None, False))
    called: list = []
    monkeypatch.setattr(zen_shim, "_kill_pid_posix",
                        lambda pid, **kw: called.append(pid))
    monkeypatch.setattr(zen_shim.os, "name", "posix")
    zen_shim._svc_stop(8898)
    assert called == []
    # Stale pid file must not linger past a failed stop.
    assert not pid_file.exists()


def test_svc_stop_windows_path_still_uses_taskkill(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    pid_file = tmp_path / "zen_shim.pid"
    pid_file.write_text("4242", encoding="ascii")
    monkeypatch.setattr(zen_shim, "_PID_FILE", str(pid_file))
    monkeypatch.setattr(zen_shim, "_svc_status", lambda port: (4242, True))
    posix_called: list = []
    monkeypatch.setattr(zen_shim, "_kill_pid_posix",
                        lambda pid, **kw: posix_called.append(pid))
    monkeypatch.setattr(zen_shim.os, "name", "nt")
    run_calls: list = []
    import subprocess
    monkeypatch.setattr(subprocess, "run",
                        lambda *a, **kw: run_calls.append(a) or None)
    assert zen_shim._svc_stop(8898) == 0
    assert posix_called == []
    assert run_calls and run_calls[0][0][0] == "taskkill"
