"""F26 — companion reference files (PAST_ATTEMPTS.md / PAST_VERIFIES.md)
+ agent._digest_failure helper. Tests cover digest extraction across
all failure_reason kinds and the lazy-load size discipline."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from Tooling import context_files, db
from Tooling.agent import (
    _ago,
    _digest_failure,
    compile_context,
)
from Tooling.manifest import Manifest


# ---------------------------------------------------------------------
# _digest_failure — pure helper covering each failure_reason
# ---------------------------------------------------------------------

def test_digest_lake_build_error_skips_lean_path_dump() -> None:
    """The dominant pre-F26 regression: failure_detail starts with a
    LEAN_PATH dump pushing the actual error past the 1000-char slice
    that agent.py was using. Digest must skip lake-trace lines and
    surface the FIRST real `error:` message."""
    detail = (
        "✖ [8369/8369] Building Problems.compactness.proofs.L_xxx (17s)\n"
        "trace: .> LEAN_PATH=D:\\Asterism\\.lake\\packages\\Cli;...\n"
        "error: Problems/x.lean:7:2: Type mismatch on `ZMod.val_natCast`\n"
        "error: Lean exited with code 1\n"
    )
    out = _digest_failure("lake_build_error", detail)
    assert "Type mismatch" in out
    assert "ZMod.val_natCast" in out
    # Must not be the LEAN_PATH dump
    assert "LEAN_PATH" not in out
    assert "lake/packages" not in out


def test_digest_lake_build_error_strips_file_line_prefix() -> None:
    """Best-effort prefix strip: ` Problems/x.lean:7:2: error: <msg>`
    digest captures `<msg>` without the file:line:col jumble."""
    detail = "error: Problems/x.lean:7:2: Type mismatch in `f`"
    out = _digest_failure("lake_build_error", detail)
    # Must include the meaningful tail
    assert "Type mismatch" in out


def test_digest_agent_no_response_short_circuits() -> None:
    """Already short — no extraction needed, just truncate to cap."""
    out = _digest_failure("agent_no_response", "claude rc=124")
    assert "claude rc=124" in out


def test_digest_forbidden_lemma_short_circuits() -> None:
    out = _digest_failure("forbidden_lemma", "ZMod.wilsons_lemma")
    assert "ZMod.wilsons_lemma" in out


def test_digest_naming_violation_short_circuits() -> None:
    out = _digest_failure(
        "naming_violation",
        "sub-goal slug 'foo' does not start with 'sNN_sub_'",
    )
    assert "naming_violation" not in out  # we only return the detail
    assert "does not start with" in out


def test_digest_empty_returns_empty() -> None:
    assert _digest_failure("lake_build_error", "") == ""
    assert _digest_failure("agent_no_response", "") == ""


def test_digest_lake_build_error_caps_length() -> None:
    """Long error messages get truncated to a sane bound for the
    1-line summary (200 chars)."""
    long = "error: " + "x" * 500
    out = _digest_failure("lake_build_error", long)
    assert len(out) <= 200


# ---------------------------------------------------------------------
# _ago — relative-time renderer
# ---------------------------------------------------------------------

def test_ago_minutes() -> None:
    past = datetime.now(timezone.utc) - timedelta(minutes=5)
    assert "min ago" in _ago(past.isoformat())


def test_ago_hours() -> None:
    past = datetime.now(timezone.utc) - timedelta(hours=2)
    assert "h ago" in _ago(past.isoformat())


def test_ago_seconds() -> None:
    past = datetime.now(timezone.utc) - timedelta(seconds=30)
    assert "s ago" in _ago(past.isoformat())


def test_ago_handles_invalid_input() -> None:
    assert _ago(None) == ""
    assert _ago("not-a-timestamp") == ""


# ---------------------------------------------------------------------
# context_files writers
# ---------------------------------------------------------------------

def _row(**kw):
    """Mimic sqlite3.Row's dict-style access for tests."""
    class _Row:
        def __init__(self, **kw):
            self._d = kw
        def __getitem__(self, k): return self._d[k]
        def keys(self): return self._d.keys()
    return _Row(**kw)


def test_write_past_attempts_creates_file_with_full_content(
    tmp_path: Path,
) -> None:
    deads = [
        _row(pipeline_id="pid-1234567890ab", failure_reason="lake_build_error",
             failure_detail="error: Type mismatch on X",
             proposal_md="## My strategy\nUse foo"),
        _row(pipeline_id="pid-2345678901bc", failure_reason="agent_no_response",
             failure_detail="claude rc=124", proposal_md=""),
    ]
    out = context_files.write_past_attempts(deads, tmp_path)
    assert out is not None
    text = out.read_text(encoding="utf-8")
    # Full failure_detail (NOT just digest) lives here
    assert "Type mismatch on X" in text
    assert "My strategy" in text
    assert "claude rc=124" in text
    assert "lake_build_error" in text
    assert "agent_no_response" in text


def test_write_past_attempts_empty_returns_none(tmp_path: Path) -> None:
    """No deads → no file written, no clutter."""
    assert context_files.write_past_attempts([], tmp_path) is None
    assert not (tmp_path / "PAST_ATTEMPTS.md").exists()


def test_write_past_verifies_creates_file(tmp_path: Path) -> None:
    rows = [
        _row(pipeline_id="pid-aaaaaaaaaaaa",
             failure_reason="lake_build_error",
             failure_detail="error: combine patch failed elaboration",
             strategy_proposal="### Decomposition\n4 sub-goals"),
    ]
    out = context_files.write_past_verifies(rows, tmp_path)
    assert out is not None
    text = out.read_text(encoding="utf-8")
    assert "combine patch failed elaboration" in text
    assert "Decomposition" in text


def test_write_past_verifies_empty_returns_none(tmp_path: Path) -> None:
    assert context_files.write_past_verifies([], tmp_path) is None


# ---------------------------------------------------------------------
# Integration: compile_context produces summary-form Context.md AND
# companion files, and Context.md stays small even with many attempts
# ---------------------------------------------------------------------

def _seed_goal(conn: sqlite3.Connection) -> int:
    conn.execute(
        "INSERT INTO problems (name, manifest_path, created_at) VALUES (?, ?, ?)",
        ("p", "Problems/p/Manifest.md", db.now()),
    )
    return db.insert_goal(
        conn, problem="p", slug="main", lean_path="Problems/p/Root.lean",
        statement="T", origin="root", difficulty=4,
    )


def _record_pipeline(conn, pid):
    conn.execute(
        "INSERT INTO pipelines (id, kind, target_id, target_kind, status,"
        " outcome, started_at, finished_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (pid, "Builder", "1", "Goal", "failed", "failed",
         db.now(), db.now()),
    )
    conn.commit()


def test_compile_context_writes_companion_past_attempts(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """End-to-end: dead_attempts → Context.md gets summary, full
    content goes to PAST_ATTEMPTS.md."""
    gid = _seed_goal(conn)
    _record_pipeline(conn, "pid-q1")
    db.record_dead_attempt(
        conn, target_id=gid, target_kind="Goal", pipeline_id="pid-q1",
        failure_reason="lake_build_error",
        failure_detail=(
            "✖ [10/10] Building x (3s)\n"
            "trace: .> LEAN_PATH=D:\\fake\\path;...\n"
            "error: Type mismatch on `Foo.bar`\n"
        ),
    )
    attempts_dir = tmp_path / ".attempts" / "pid-q1"
    attempts_dir.mkdir(parents=True)
    goal = db.get_goal(conn, gid)
    out = compile_context(conn, goal=goal, mfst=Manifest(problem="p", statement="T"),
                          attempts_dir=attempts_dir)
    text = out.read_text(encoding="utf-8")

    # Context.md: summary line with digest + pointer
    assert "Previous attempts on THIS goal" in text
    assert "Type mismatch on `Foo.bar`" in text  # digest extracted
    assert "PAST_ATTEMPTS.md" in text  # pointer present
    # Context.md must NOT contain the LEAN_PATH dump anymore
    assert "LEAN_PATH=" not in text

    # Companion file has the full content
    past = (attempts_dir / "PAST_ATTEMPTS.md").read_text(encoding="utf-8")
    assert "LEAN_PATH=" in past  # full stderr preserved here
    assert "Foo.bar" in past


def test_compile_context_size_drop_with_many_attempts(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """Quantitative goal: even 5 attempts each carrying ~2KB of
    failure_detail must not blow up Context.md. F26's design budget
    is ~5x reduction vs the pre-F26 raw-blob approach."""
    gid = _seed_goal(conn)
    big_stderr_template = (
        "✖ [N/N] Building x\n"
        "trace: .> LEAN_PATH=" + "x" * 1500 + "\n"
        "error: Type mismatch line {n}\n"
    )
    for i in range(5):
        pid = f"pid-attempt-{i:02d}"
        _record_pipeline(conn, pid)
        db.record_dead_attempt(
            conn, target_id=gid, target_kind="Goal", pipeline_id=pid,
            failure_reason="lake_build_error",
            failure_detail=big_stderr_template.format(n=i),
            proposal_md="## Strategy " + "y" * 1000,
        )

    attempts_dir = tmp_path / ".attempts" / "pid-current"
    attempts_dir.mkdir(parents=True)
    goal = db.get_goal(conn, gid)
    out = compile_context(conn, goal=goal,
                          mfst=Manifest(problem="p", statement="T"),
                          attempts_dir=attempts_dir)
    ctx_size = out.stat().st_size
    past_size = (attempts_dir / "PAST_ATTEMPTS.md").stat().st_size

    # Pre-F26 with 5 attempts × (1000 char detail + 2000 char proposal)
    # ≈ 15 KB inline. F26 budget: Context.md should be well under 3 KB.
    assert ctx_size < 3000, f"Context.md too big: {ctx_size}B"
    # Full content lives in companion file (which is allowed to be big)
    assert past_size > 5000


def test_compile_context_no_companion_when_no_history(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """Fresh goal, no dead_attempts → no PAST_ATTEMPTS.md emitted."""
    gid = _seed_goal(conn)
    attempts_dir = tmp_path / ".attempts" / "pid-fresh"
    attempts_dir.mkdir(parents=True)
    goal = db.get_goal(conn, gid)
    compile_context(conn, goal=goal,
                    mfst=Manifest(problem="p", statement="T"),
                    attempts_dir=attempts_dir)
    assert not (attempts_dir / "PAST_ATTEMPTS.md").exists()
    assert not (attempts_dir / "PAST_VERIFIES.md").exists()
