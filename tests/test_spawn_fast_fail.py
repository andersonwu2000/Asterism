"""F46 — defense against claude.exe instant-fail loops.

A spawn that returns rc≠0 in <10s wall-clock is almost certainly an
infra fault (CLI crash on launch, prompt parser reject, cwd unreachable,
transient network) rather than an agent error. Three things must work:

1. Provider writes captured stderr to `attempts_dir/_spawn.stderr` so
   the cause is no longer black-boxed.
2. Pipeline reclassifies short rc≠0 calls as `spawn_fast_fail` and
   includes the stderr tail in `failure_detail`.
3. cascade_one detects spawn_fast_fail rows via DB lookup and skips
   `increment_goal_attempts` so a transient infra blip doesn't burn
   the goal's attempts cap.

Daemon-loop cool-down + global-bound counter are exercised manually in
production (no easy unit harness for the threaded loop); the unit-level
contract here is sufficient to keep the regression from reappearing.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
import pytest

from Tooling import db, pipeline as _pipeline
from Tooling.dispatcher import cascade_one


# ---------------------------------------------------------------------
# 1. Provider stderr capture
# ---------------------------------------------------------------------

def test_claude_spawn_writes_stderr_on_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """rc≠0 → write `attempts_dir/_spawn.stderr` with the captured
    stderr. Skip on rc=0 to keep the sandbox tidy."""
    import subprocess as _sub
    from Tooling.llm import claude_cli, base
    monkeypatch.setattr(claude_cli.shutil, "which", lambda _: "/fake/claude")
    monkeypatch.setattr(
        claude_cli.subprocess, "run",
        lambda *a, **kw: _sub.CompletedProcess(
            args=a[0], returncode=1, stdout="",
            stderr="claude: prompt parse error at line 3"))
    (tmp_path / "p.md").write_text("body", encoding="utf-8")
    p = claude_cli.ClaudeCliProvider()
    p.spawn(base.LLMRequest(
        kind="backward", prompt_path=tmp_path / "p.md",
        problem_dir=tmp_path, attempts_dir=tmp_path, timeout_sec=60,
    ))
    sf = tmp_path / "_spawn.stderr"
    assert sf.exists()
    body = sf.read_text(encoding="utf-8")
    assert "rc=1" in body
    assert "prompt parse error" in body


def test_claude_spawn_skips_stderr_file_on_success(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """rc=0 → don't write _spawn.stderr (avoid clutter)."""
    import subprocess as _sub
    from Tooling.llm import claude_cli, base
    monkeypatch.setattr(claude_cli.shutil, "which", lambda _: "/fake/claude")
    monkeypatch.setattr(
        claude_cli.subprocess, "run",
        lambda *a, **kw: _sub.CompletedProcess(
            args=a[0], returncode=0, stdout="ok", stderr=""))
    (tmp_path / "p.md").write_text("body", encoding="utf-8")
    p = claude_cli.ClaudeCliProvider()
    p.spawn(base.LLMRequest(
        kind="backward", prompt_path=tmp_path / "p.md",
        problem_dir=tmp_path, attempts_dir=tmp_path, timeout_sec=60,
    ))
    assert not (tmp_path / "_spawn.stderr").exists()


def test_claude_spawn_writes_timeout_stderr(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Timeout (rc=124) gets a synthetic _spawn.stderr noting the
    timeout. Without this the rc=124 case left no forensic trail."""
    import subprocess as _sub
    from Tooling.llm import claude_cli, base
    monkeypatch.setattr(claude_cli.shutil, "which", lambda _: "/fake/claude")

    def _timeout(*a, **kw):
        raise _sub.TimeoutExpired(cmd=a[0], timeout=1)
    monkeypatch.setattr(claude_cli.subprocess, "run", _timeout)
    (tmp_path / "p.md").write_text("body", encoding="utf-8")
    p = claude_cli.ClaudeCliProvider()
    rc = p.spawn(base.LLMRequest(
        kind="backward", prompt_path=tmp_path / "p.md",
        problem_dir=tmp_path, attempts_dir=tmp_path, timeout_sec=1,
    ))
    assert rc == 124
    body = (tmp_path / "_spawn.stderr").read_text(encoding="utf-8")
    assert "TimeoutExpired" in body


def test_gemini_spawn_writes_stderr_on_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Mirror behavior in gemini_cli."""
    import subprocess as _sub
    from Tooling.llm import gemini_cli, base
    monkeypatch.setattr(gemini_cli.shutil, "which", lambda _: "/fake/gemini")
    monkeypatch.setattr(
        gemini_cli.subprocess, "run",
        lambda *a, **kw: _sub.CompletedProcess(
            args=a[0], returncode=2, stdout="",
            stderr="gemini: 401 Unauthorized"))
    (tmp_path / "p.md").write_text("body", encoding="utf-8")
    p = gemini_cli.GeminiCliProvider()
    p.spawn(base.LLMRequest(
        kind="backward", prompt_path=tmp_path / "p.md",
        problem_dir=tmp_path, attempts_dir=tmp_path, timeout_sec=60,
    ))
    body = (tmp_path / "_spawn.stderr").read_text(encoding="utf-8")
    assert "rc=2" in body
    assert "401 Unauthorized" in body


# ---------------------------------------------------------------------
# 2. Pipeline classifies spawn_fast_fail
# ---------------------------------------------------------------------

def test_spawn_failure_classifies_fast_as_spawn_fast_fail(
    tmp_path: Path,
) -> None:
    """Spawn duration < SPAWN_FAST_FAIL_SEC (10s) and rc≠0 → reason
    is `spawn_fast_fail`, not `agent_rc_nonzero`."""
    reason, detail = _pipeline._spawn_failure(
        rc=1, attempts_dir=tmp_path, spawn_dur=2.3)
    assert reason == "spawn_fast_fail"
    assert "fast-fail" in detail
    assert "2.3s" in detail


def test_spawn_failure_classifies_timeout_as_agent_timeout(
    tmp_path: Path,
) -> None:
    """rc=124 (SIGKILL after WORKER_TIMEOUT_SEC) → `agent_timeout`."""
    reason, _ = _pipeline._spawn_failure(
        rc=124, attempts_dir=tmp_path, spawn_dur=600.0)
    assert reason == "agent_timeout"


def test_spawn_failure_classifies_slow_nontimeout_as_rc_nonzero(
    tmp_path: Path,
) -> None:
    """rc≠0 and rc≠124, wall ≥ 10s → generic `agent_rc_nonzero`."""
    reason, _ = _pipeline._spawn_failure(
        rc=1, attempts_dir=tmp_path, spawn_dur=15.0)
    assert reason == "agent_rc_nonzero"


def test_spawn_failure_includes_stderr_tail(tmp_path: Path) -> None:
    """When _spawn.stderr exists, its first ~600 chars are folded into
    failure_detail so dead_attempts isn't a black box."""
    (tmp_path / "_spawn.stderr").write_text(
        "rc=1\nclaude: cannot read file foo/bar.md", encoding="utf-8")
    _, detail = _pipeline._spawn_failure(
        rc=1, attempts_dir=tmp_path, spawn_dur=1.5)
    assert "cannot read file foo/bar.md" in detail


def test_spawn_failure_handles_missing_stderr_file(tmp_path: Path) -> None:
    """No _spawn.stderr (provider didn't write it for some reason) →
    fall back to just `agent rc=N` text. Must not raise."""
    reason, detail = _pipeline._spawn_failure(
        rc=1, attempts_dir=tmp_path, spawn_dur=2.0)
    assert reason == "spawn_fast_fail"
    assert "rc=1" in detail


# ---------------------------------------------------------------------
# 3. cascade_one skips increment for spawn_fast_fail
# ---------------------------------------------------------------------

def _seed_goal(conn: sqlite3.Connection, *, problem: str = "p") -> int:
    conn.execute(
        "INSERT INTO problems (name, manifest_path, created_at) VALUES (?, ?, ?)",
        (problem, "Problems/p/Manifest.md", db.now()),
    )
    return db.insert_goal(
        conn, problem=problem, slug="main", lean_path="Problems/p/Root.lean",
        statement="T", origin="root",
    )


def _record_dead_attempt(conn: sqlite3.Connection, *, pipeline_id: str,
                         target_id: int, reason: str,
                         kind: str = "Builder") -> None:
    """Mimic what pipeline.run_* does: insert a pipelines row + a
    dead_attempts row pointing at it. dead_attempts.pipeline_id has a
    FK to pipelines.id so the parent row must exist."""
    conn.execute(
        "INSERT INTO pipelines (id, kind, target_id, target_kind, "
        "status, outcome, started_at, finished_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (pipeline_id, kind, str(target_id), "Goal", "failed", "failed",
         db.now(), db.now()),
    )
    conn.execute(
        "INSERT INTO dead_attempts (target_id, target_kind, pipeline_id, "
        "failure_reason, failure_detail, ts) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (target_id, "Goal", pipeline_id, reason, "", db.now()),
    )
    conn.commit()


def test_cascade_builder_spawn_fast_fail_skips_increment(
    conn: sqlite3.Connection,
) -> None:
    """The whole point of F46: a Builder spawn_fast_fail must NOT
    increment the goal's attempts counter. Otherwise three 2-second
    rc=1 bursts torch the cap and shelve a salvageable goal."""
    gid = _seed_goal(conn)
    pid = "fast-fail-pid"
    cascade_one(conn, pipeline_id=pid, kind="Builder",
                target_id=str(gid), target_kind="Goal", outcome="failed",
                failure_reason="spawn_fast_fail")
    row = db.get_goal(conn, gid)
    assert row["attempts"] == 0
    assert row["status"] == "open"


def test_cascade_backward_spawn_fast_fail_skips_increment(
    conn: sqlite3.Connection,
) -> None:
    """Same skip applies to Backward. The 2026-05-02 compactness run
    burned 3 of 8 attempts on Goal 129 via 2-second Backward rc=1
    bursts before the Backward branch was even taken seriously."""
    gid = _seed_goal(conn)
    pid = "fast-fail-bwd"
    cascade_one(conn, pipeline_id=pid, kind="Backward",
                target_id=str(gid), target_kind="Goal", outcome="failed",
                failure_reason="spawn_fast_fail")
    row = db.get_goal(conn, gid)
    assert row["attempts"] == 0


def test_cascade_normal_failure_still_increments(
    conn: sqlite3.Connection,
) -> None:
    """Defense-in-depth: failure_reason='lake_build_error' is a real
    agent failure → increment attempts as before. F46 only changes
    the spawn_fast_fail path."""
    gid = _seed_goal(conn)
    pid = "real-fail"
    cascade_one(conn, pipeline_id=pid, kind="Builder",
                target_id=str(gid), target_kind="Goal", outcome="failed",
                failure_reason="lake_build_error")
    assert db.get_goal(conn, gid)["attempts"] == 1


# ---------------------------------------------------------------------
# 4. bfs_refill respects cooldown_until
# ---------------------------------------------------------------------

def test_bfs_refill_skips_cooled_target(
    conn: sqlite3.Connection,
) -> None:
    """When (target,kind) cooldown_until is in the future, bfs_refill
    does not enqueue. Once the cooldown expires it resumes normally."""
    import time
    from Tooling.dispatcher import bfs_refill
    gid = _seed_goal(conn)
    cooldown_until = {(str(gid), "Builder"): time.time() + 60.0}
    bfs_refill(conn, set(), cooldown_until)
    assert db.queue_size(conn) == 0


def test_bfs_refill_dispatches_when_cooldown_expired(
    conn: sqlite3.Connection,
) -> None:
    import time
    from Tooling.dispatcher import bfs_refill
    gid = _seed_goal(conn)
    # Cooldown already in the past — should NOT block
    cooldown_until = {(str(gid), "Builder"): time.time() - 1.0}
    bfs_refill(conn, set(), cooldown_until)
    assert db.queue_size(conn) == 1


def test_bfs_refill_no_cooldown_dict_back_compat(
    conn: sqlite3.Connection,
) -> None:
    """Existing tests (and any external callers) still pass running
    only — cooldown_until=None must mean "no cooldown anywhere"."""
    from Tooling.dispatcher import bfs_refill
    gid = _seed_goal(conn)
    bfs_refill(conn, set())  # no cooldown arg
    assert db.queue_size(conn) == 1
