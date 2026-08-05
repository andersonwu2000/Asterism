"""Daemon breakaway + code-drift handoff (2026-07-10).

The daemon must not be its starter's child (taskkill /T on the serve
process reaped a live marathon), and losing the implicit
"serve restart = new daemon code" coupling is compensated by a
MECHANISM, not discipline: the daemon fingerprints the tree at boot,
drains on drift, and hands off to a lock-waiting successor.
"""
from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from Tooling.core import cli as _cli
from Tooling.core import dispatcher as _disp


class _FakeRelay:
    """Stands in for both spawn shapes: the Windows relay (communicate
    prints the daemon pid) and the POSIX direct child (pid attr)."""
    pid = 4242

    def communicate(self, timeout=None):
        return b"4242\n", b""


def _register_problem(workspace: Path, name: str = "p") -> None:
    """#158 precondition: a scoped `daemon_start` refuses unless the
    scope LIKE-matches a registered problem."""
    from Tooling.state import db as _db
    c = _db.connect(workspace / "asterism.db")
    _db.init_schema(c)
    c.execute("INSERT INTO problems (name, manifest_path, created_at,"
              " bootstrap_done) VALUES (?, '', ?, 1)", (name, _db.now()))
    c.commit()
    c.close()


def test_daemon_start_spawns_through_a_relay_on_windows(
        tmp_path: Path, monkeypatch) -> None:
    """The daemon must not be the caller's child: on Windows the spawn
    goes through a `-c` relay that exits at once, breaking the
    parent-child chain taskkill /T walks."""
    if os.name != "nt":
        pytest.skip("Windows process-tree semantics")
    calls: list = []

    def fake_popen(argv, **kw):
        calls.append((argv, kw))
        return _FakeRelay()

    monkeypatch.setattr(_cli, "_daemon_live_pid", lambda ws: None)
    import subprocess
    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    _register_problem(tmp_path)
    rc, msg = _cli.daemon_start(tmp_path, scope="p")
    assert rc == 0
    argv, kw = calls[0]
    assert argv[1] == "-c"                      # the relay script
    assert "4242" in msg                        # relay reported the real pid
    # the actual daemon argv rides behind (cwd, log, ...cmd)
    assert "Tooling.core.cli" in argv
    assert "--scope" in argv and "p" in argv
    assert kw["creationflags"] & 0x00000008     # DETACHED_PROCESS


def test_daemon_start_wait_lock_retries_until_the_lock_frees(
        tmp_path: Path, monkeypatch) -> None:
    """The handoff waiter parks on the refusal until the dying daemon's
    lock frees, then starts — without wait_lock_sec it refuses at once
    (unchanged behaviour)."""
    live: list = [111, 111, None]  # two refusals, then free
    monkeypatch.setattr(_cli, "_daemon_live_pid",
                        lambda ws: live.pop(0) if live else None)
    import subprocess
    monkeypatch.setattr(subprocess, "Popen",
                        lambda *a, **k: _FakeRelay())
    monkeypatch.setattr(time, "sleep", lambda s: None)
    _register_problem(tmp_path)
    rc, msg = _cli.daemon_start(tmp_path, scope="p", wait_lock_sec=30.0)
    assert rc == 0

    # and the zero-wait path still refuses immediately
    monkeypatch.setattr(_cli, "_daemon_live_pid", lambda ws: 222)
    rc, msg = _cli.daemon_start(tmp_path, scope="p")
    assert rc == 1
    assert "REFUSED" in msg


def test_spawn_handoff_successor_argv_shape(
        tmp_path: Path, monkeypatch) -> None:
    """The successor is a lock-waiting `daemon start` with the SAME
    scope — and (on Windows) breaks away from the dying daemon's
    kill-on-close job, or it would die with it."""
    calls: list = []
    import subprocess
    monkeypatch.setattr(subprocess, "Popen",
                        lambda argv, **kw: calls.append((argv, kw)))
    _disp._spawn_handoff_successor(tmp_path, "Putnam.p")
    argv, kw = calls[0]
    assert argv[2:6] == ["Tooling.core.cli", "daemon", "start", "--wait-lock"]
    assert "--scope" in argv and "Putnam.p" in argv
    if os.name == "nt":
        assert kw["creationflags"] & 0x00000008

    # scope-less runs hand off scope-less (--all-problems semantics)
    calls.clear()
    _disp._spawn_handoff_successor(tmp_path, None)
    argv, _ = calls[0]
    assert "--scope" not in argv


def test_daemon_status_reports_code_stale(
        tmp_path: Path, monkeypatch) -> None:
    """While a daemon runs code older than the tree, status says so —
    the visible half of the drift-handoff mechanism."""
    logs = tmp_path / ".asterism" / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    (logs / "daemon-fp.txt").write_text("OLD", encoding="utf-8")
    (tmp_path / ".asterism" / "daemon.pid").write_text(
        "999\n1000.0\n", encoding="utf-8")
    monkeypatch.setattr(_cli, "_daemon_live_pid", lambda ws: 999)
    from Tooling.lsp import lifecycle as gwl
    monkeypatch.setattr(gwl, "code_fingerprint", lambda: "NEW")
    st = _cli.daemon_status(tmp_path)
    assert st["running"] is True
    assert st["code_stale"] is True
    monkeypatch.setattr(gwl, "code_fingerprint", lambda: "OLD")
    assert _cli.daemon_status(tmp_path)["code_stale"] is False


def test_config_fingerprint_tracks_yaml_and_env(tmp_path: Path) -> None:
    """Config drift handoff (2026-07-18): the fingerprint must move when
    Asterism.yaml or .env changes (the UI writes yaml; .env is the
    manual override) and stay put otherwise - missing files are a
    stable state, not an error."""
    from Tooling.lsp.lifecycle import config_fingerprint
    fp_empty = config_fingerprint(tmp_path)
    assert fp_empty == config_fingerprint(tmp_path)  # stable when absent

    (tmp_path / "Asterism.yaml").write_text(
        "strategist:\n  model: claude-opus-4-8\n", encoding="utf-8")
    fp_yaml = config_fingerprint(tmp_path)
    assert fp_yaml != fp_empty

    (tmp_path / ".env").write_text(
        "ASTERISM_FORWARD_MODEL=claude-sonnet-5\n", encoding="utf-8")
    fp_env = config_fingerprint(tmp_path)
    assert fp_env != fp_yaml
    assert fp_env == config_fingerprint(tmp_path)  # stable between edits


def test_config_fingerprint_is_not_part_of_code_fingerprint(
        tmp_path: Path) -> None:
    """A settings edit must NOT flip the gateway's stale check - models
    and knobs are daemon-side; re-warming the gateway for them would be
    pure waste. code_fingerprint covers Tooling *.py only."""
    from Tooling.lsp.lifecycle import code_fingerprint
    before = code_fingerprint()
    (tmp_path / "Asterism.yaml").write_text("x: 1\n", encoding="utf-8")
    assert code_fingerprint() == before
