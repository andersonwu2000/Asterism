"""F28 — daemon log path: .asterism/logs/<problem>_<model>_<ts>.log
+ retention. Tests cover filename derivation, retention pruning, and
the Tee stream that mirrors stdout to disk + terminal."""
from __future__ import annotations

import io
import os
import time
from pathlib import Path

import pytest

from Tooling.core.cli import (
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
    """`<problem>_<ts>.log` with ts in YYYYMMDD-HHMMSS UTC.

    No model token: it was resolved from `builder` + `backward`, keys
    the v33 Formalizer merge retired, so it always printed
    DEFAULT_MODEL — 2026-08-06's log reads `claude-sonnet-4-6` for a run
    whose formalizer was gemini and whose strategist was opus-5. The
    seats now go in the log's first lines (`seat_banner`), where one
    line per pipeline can be true."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ASTERISM_AGENT_MODEL", "claude-sonnet-4-6")
    name = _log_filename(tmp_path)
    # No DB → 'daemon' fallback
    assert name.startswith("daemon_")
    assert name.endswith(".log")
    # a model name must not reappear here by any route
    assert "claude" not in name and "gemini" not in name
    # ts portion is 16 chars: 8 date + '-' + 6 time + 'Z' (UTC,
    # self-documented — E fix 2026-07-24)
    ts = name.removesuffix(".log").rsplit("_", 1)[1]
    assert len(ts) == 16 and ts[8] == "-" and ts.endswith("Z")
    assert ts[:8].isdigit() and ts[9:15].isdigit()


def test_seat_banner_names_every_pipelines_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """What the filename used to claim, where it can be accurate: one
    line per spawning pipeline with its provider/model."""
    from Tooling.core.cli import seat_banner
    from Tooling.core import dispatcher
    monkeypatch.setattr(dispatcher, "_pipeline_seats", lambda: {
        "strategist": ("claude", "claude-opus-5"),
        "formalizer": ("antigravity", "gemini-3.6-flash-high"),
    })
    out = seat_banner()
    assert "[seats] strategist: claude/claude-opus-5" in out
    assert "[seats] formalizer: antigravity/gemini-3.6-flash-high" in out


def test_seat_banner_never_blocks_a_run(monkeypatch: pytest.MonkeyPatch):
    """A banner is diagnostics. If it cannot be built, the run starts
    anyway — the alternative is a daemon that will not boot because a
    log header failed."""
    from Tooling.core.cli import seat_banner
    from Tooling.core import dispatcher

    def boom():
        raise RuntimeError("config unreadable")
    monkeypatch.setattr(dispatcher, "_pipeline_seats", boom)
    assert seat_banner() == "[seats] unavailable"


def test_log_filename_uses_single_problem(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If exactly one problem in DB, that name appears in the log file."""
    from Tooling.state import db
    monkeypatch.chdir(tmp_path)
    conn = db.connect()
    db.init_schema(conn)
    conn.execute(
        "INSERT INTO problems (name, manifest_path, created_at, bootstrap_done)"
        " VALUES ('wilson', 'Problems/wilson/Manifest.md', ?, 1)",
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
    from Tooling.state import db
    monkeypatch.chdir(tmp_path)
    conn = db.connect()
    db.init_schema(conn)
    for p in ("wilson", "compactness"):
        conn.execute(
            "INSERT INTO problems (name, manifest_path, created_at, bootstrap_done)"
            " VALUES (?, ?, ?, 1)",
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


def test_tee_survives_unencodable_char_on_one_stream(tmp_path: Path) -> None:
    """BT 2026-05-29 g3410: a Lean goal carries `∃` (U+2203); a legacy
    cp950 console raised UnicodeEncodeError on write, killing the
    pipeline and mis-recording it as a lake_build_error. _Tee must
    swallow a per-stream write failure and still deliver the text to the
    surviving (UTF-8 log) stream."""
    class _Cp950Console:
        def write(self, s):
            s.encode("cp950")  # raises on ∃, exactly like the real console
            return len(s)
        def flush(self):
            pass
    good = io.StringIO()
    tee = _Tee(_Cp950Console(), good)
    n = tee.write("rotation ∃ R, P R\n")  # must NOT raise
    assert n == len("rotation ∃ R, P R\n")
    assert good.getvalue() == "rotation ∃ R, P R\n"


def test_cmd_run_logs_traceback_on_crash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A `dispatcher.run` crash must leave its traceback in the daemon log.

    Regression: cmd_run's `finally` restored `sys.stderr` + closed the log
    file BEFORE an unhandled exception propagated to the interpreter's default
    handler — so a daemon crash left `.asterism/logs/multi_*.log` ending
    mid-tick with NO traceback. The green_theorem stress-test daemon
    self-terminated and the crash was invisible for exactly this reason
    (the log stopped cleanly at a `[dispatch] …` line)."""
    import argparse
    from Tooling.core import cli
    monkeypatch.chdir(tmp_path)

    def _boom(*_a, **_k):
        raise RuntimeError("dispatcher exploded mid-tick")
    monkeypatch.setattr(cli.dispatcher, "run", _boom)
    # Stub the zombie-lock hard-exit seam (production os._exit would take
    # the test runner with it); record that it fired with rc=2.
    exited = {"rc": None}
    monkeypatch.setattr(cli, "_hard_exit_after_fatal",
                        lambda rc: exited.__setitem__("rc", rc))

    args = argparse.Namespace(scope="Geometry.green_theorem", once=False,
                              all_problems=False)
    with pytest.raises(RuntimeError, match="exploded mid-tick"):
        cli.cmd_run(args)

    # The FATAL path must request a hard process exit (zombie-lock guard:
    # non-daemon pool threads otherwise keep holding daemon.pid).
    assert exited["rc"] == 2

    logs = list((tmp_path / LOG_DIR).glob("*.log"))
    assert logs, "no daemon log written"
    text = logs[0].read_text(encoding="utf-8")
    assert "FATAL: unhandled exception" in text
    assert "RuntimeError: dispatcher exploded mid-tick" in text
    assert "Traceback (most recent call last)" in text


def test_force_utf8_io_idempotent_and_sets_child_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """_force_utf8_io exports UTF-8 to the child-process env and is safe
    to call when streams don't support reconfigure (pytest capture)."""
    from Tooling.core.cli import _force_utf8_io
    monkeypatch.delenv("PYTHONUTF8", raising=False)
    monkeypatch.delenv("PYTHONIOENCODING", raising=False)
    _force_utf8_io()  # must not raise under captured streams
    assert os.environ["PYTHONUTF8"] == "1"
    assert os.environ["PYTHONIOENCODING"] == "utf-8"
