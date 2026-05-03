"""F28 — daemon log path: .asterism/logs/<problem>_<model>_<ts>.log
+ retention. Tests cover filename derivation, retention pruning, and
the Tee stream that mirrors stdout to disk + terminal."""
from __future__ import annotations

import io
import os
import time
from pathlib import Path

import pytest

from Tooling.cli import (
    LOG_DIR,
    LOG_RETENTION_KEEP,
    _Tee,
    _log_filename,
    _open_run_log,
    _retain_recent_logs,
)


# ---------------------------------------------------------------------
# _log_filename — naming convention
# ---------------------------------------------------------------------

def test_log_filename_format(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`<problem>_<model>_<ts>.log` with ts in YYYYMMDD-HHMMSS UTC."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ASTERISM_AGENT_MODEL", "claude-sonnet-4-6")
    name = _log_filename(tmp_path)
    # No DB → 'daemon' fallback
    assert name.startswith("daemon_claude-sonnet-4-6_")
    assert name.endswith(".log")
    # ts portion is 15 chars: 8 date + '-' + 6 time
    ts = name.removesuffix(".log").rsplit("_", 1)[1]
    assert len(ts) == 15 and ts[8] == "-"
    assert ts[:8].isdigit() and ts[9:].isdigit()


def test_log_filename_reflects_mixed_models(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """P1-#8: when builder and backward use different models (F39 per-
    pipeline selection), filename combines them with `+` so the
    operator can tell at a glance — instead of always reporting the
    legacy ASTERISM_AGENT_MODEL value (which lied for mixed runs)."""
    monkeypatch.chdir(tmp_path)
    # Clear legacy fallback
    monkeypatch.delenv("ASTERISM_AGENT_MODEL", raising=False)
    monkeypatch.setenv("ASTERISM_BUILDER_MODEL", "claude-sonnet-4-6")
    monkeypatch.setenv("ASTERISM_BACKWARD_MODEL", "claude-opus-4-7")
    name = _log_filename(tmp_path)
    assert "claude-sonnet-4-6+claude-opus-4-7" in name


def test_log_filename_collapses_when_models_match(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """P1-#8: when both kinds resolve to the same model, no `+`
    appears — keeps the common case clean."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ASTERISM_AGENT_MODEL", raising=False)
    monkeypatch.setenv("ASTERISM_BUILDER_MODEL", "claude-opus-4-7")
    monkeypatch.setenv("ASTERISM_BACKWARD_MODEL", "claude-opus-4-7")
    name = _log_filename(tmp_path)
    assert "claude-opus-4-7_" in name
    assert "+" not in name


def test_log_filename_uses_single_problem(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If exactly one problem in DB, that name appears in the log file."""
    from Tooling import db
    monkeypatch.chdir(tmp_path)
    conn = db.connect()
    db.init_schema(conn)
    conn.execute(
        "INSERT INTO problems (name, manifest_path, created_at)"
        " VALUES ('wilson', 'Problems/wilson/Manifest.md', ?)",
        (db.now(),),
    )
    conn.commit()
    conn.close()
    name = _log_filename(tmp_path)
    assert name.startswith("wilson_")


def test_log_filename_multi_when_many(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Multiple problems → 'multi' tag (we don't pick a winner)."""
    from Tooling import db
    monkeypatch.chdir(tmp_path)
    conn = db.connect()
    db.init_schema(conn)
    for p in ("wilson", "compactness"):
        conn.execute(
            "INSERT INTO problems (name, manifest_path, created_at)"
            " VALUES (?, ?, ?)",
            (p, f"Problems/{p}/Manifest.md", db.now()),
        )
    conn.commit()
    conn.close()
    name = _log_filename(tmp_path)
    assert name.startswith("multi_")


def test_log_filename_sanitizes_model_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Path-unsafe chars in ASTERISM_AGENT_MODEL get replaced so the
    filename is always usable. (Real model names don't have these,
    but defensive against env injection / typos.)"""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ASTERISM_AGENT_MODEL", "weird/name:bad")
    name = _log_filename(tmp_path)
    assert "/" not in name and ":" not in name


# ---------------------------------------------------------------------
# _open_run_log — directory creation + retention
# ---------------------------------------------------------------------

def test_open_run_log_creates_log_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    p = _open_run_log(tmp_path)
    assert p.parent == tmp_path / LOG_DIR
    assert (tmp_path / LOG_DIR).is_dir()
    assert p.suffix == ".log"
    # File itself isn't created by _open_run_log; caller opens it.
    assert not p.exists()


def test_retain_recent_logs_keeps_n_newest(tmp_path: Path) -> None:
    """Old logs beyond `keep` are deleted; newest survive."""
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    for i in range(5):
        p = log_dir / f"x_{i}.log"
        p.write_text("", encoding="utf-8")
        # Stagger mtimes so sort order is deterministic
        os.utime(p, (i, i))

    deleted = _retain_recent_logs(log_dir, keep=2)
    remaining = sorted(p.name for p in log_dir.glob("*.log"))
    # 2 newest remain (mtimes 4, 3)
    assert remaining == ["x_3.log", "x_4.log"]
    # 3 deletions reported
    assert len(deleted) == 3


def test_retain_recent_logs_under_threshold_noop(tmp_path: Path) -> None:
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    for i in range(2):
        (log_dir / f"x_{i}.log").write_text("", encoding="utf-8")
    deleted = _retain_recent_logs(log_dir, keep=10)
    assert deleted == []
    assert len(list(log_dir.glob("*.log"))) == 2


def test_retain_recent_logs_missing_dir_returns_empty(
    tmp_path: Path,
) -> None:
    """Defensive: pre-init directory absent → no crash."""
    assert _retain_recent_logs(tmp_path / "nope", keep=5) == []


def test_open_run_log_triggers_retention(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Calling _open_run_log when the dir already has > keep files
    prunes the oldest ones. Default `keep` is LOG_RETENTION_KEEP."""
    monkeypatch.chdir(tmp_path)
    log_dir = tmp_path / LOG_DIR
    log_dir.mkdir(parents=True)
    # Seed with 25 fake logs (above the 20 default)
    for i in range(25):
        p = log_dir / f"old_{i:02d}.log"
        p.write_text("", encoding="utf-8")
        os.utime(p, (i, i))
    # New log path requested
    _open_run_log(tmp_path)
    surviving = sorted(p.name for p in log_dir.glob("*.log"))
    assert len(surviving) == LOG_RETENTION_KEEP


# ---------------------------------------------------------------------
# _Tee — write to stdout AND file
# ---------------------------------------------------------------------

def test_tee_writes_to_all_streams(tmp_path: Path) -> None:
    a = io.StringIO()
    b = io.StringIO()
    tee = _Tee(a, b)
    n = tee.write("hello\n")
    assert n == 6
    assert a.getvalue() == "hello\n"
    assert b.getvalue() == "hello\n"


def test_tee_flush_propagates(tmp_path: Path) -> None:
    """flush() must propagate to all wrapped streams (otherwise
    background daemon `print(..., flush=True)` would still buffer in
    the file stream)."""
    log_path = tmp_path / "x.log"
    f = log_path.open("w", encoding="utf-8")
    tee = _Tee(io.StringIO(), f)
    tee.write("x")
    tee.flush()
    # Read while file still open: data must already be on disk
    f.close()
    assert log_path.read_text(encoding="utf-8") == "x"


def test_tee_isatty_reports_primary() -> None:
    """Some downstream tools query isatty(); report the primary
    stream's value (terminal), not the log file's (always False)."""
    class _Tty:
        def isatty(self): return True
    tee = _Tee(_Tty(), io.StringIO())
    assert tee.isatty() is True
