"""F53 — Same-session Backward retry (mirror of F33 for Builder).

When run_backward fails (lake_build_error etc.), the goal's
`backward_session_id` persists so the next dispatch resumes the
agent's session via `claude --resume` with the prior lake stderr
inlined as `retry_context`. Tests assert the session-id mechanics +
the timeout-clears-session safety net, mocking spawn_llm so no
actual claude/lake invocation happens.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from Tooling import agent, db, manifest, pipeline


def _seed_root_goal(tmp_path: Path, conn: sqlite3.Connection) -> int:
    problem = "p"
    pdir = tmp_path / "Problems" / problem
    pdir.mkdir(parents=True)
    (pdir / "Manifest.md").write_text(
        "---\nproblem: p\n---\n## Statement\nTrue\n", encoding="utf-8")
    conn.execute(
        "INSERT INTO problems (name, manifest_path, created_at) "
        "VALUES (?, ?, ?)",
        (problem, str(pdir / "Manifest.md"), db.now()))
    conn.commit()
    root = pdir / "Root.lean"
    root.write_text(
        "import Mathlib\nnamespace Problems.p\n"
        "theorem main : True := by sorry\n"
        "end Problems.p\n",
        encoding="utf-8")
    rel = root.relative_to(tmp_path).as_posix()
    return db.insert_goal(
        conn, problem=problem, slug="main", lean_path=rel,
        statement="True", origin="root", depth=0,
    )


def test_first_dispatch_mints_session_id_and_passes_to_spawn(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No prior session → run_backward mints a UUID, persists it,
    passes session_id + is_retry=False to spawn_llm."""
    gid = _seed_root_goal(tmp_path, conn)
    captured = {}

    def fake_spawn(**kw):
        captured.update(kw)
        return 124  # bail out via timeout path; we only care about call args

    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)

    pipeline.run_backward(
        conn, goal_id=gid, workspace=tmp_path,
        mfst=manifest.Manifest(problem="p", statement="True"),
        pipeline_id="pid-bw1",
    )
    assert captured["session_id"] is not None
    assert captured["is_retry"] is False
    assert captured["retry_context"] is None
    # On rc=124 (timeout) session is conservatively cleared
    assert db.get_backward_session_id(conn, gid) is None


def test_second_dispatch_reuses_session_with_retry_context(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prior session + a recorded Backward dead_attempt → second
    dispatch sets is_retry=True and inlines the prior lake stderr."""
    gid = _seed_root_goal(tmp_path, conn)
    db.set_backward_session_id(conn, gid, "saved-uuid")
    # Simulate a prior Backward dead_attempt with a lake error
    conn.execute(
        "INSERT INTO pipelines (id, kind, target_id, target_kind, "
        "status, outcome, started_at, finished_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("pid-prior", "Backward", str(gid), "Goal",
         "failed", "failed", db.now(), db.now()),
    )
    conn.execute(
        "INSERT INTO dead_attempts (target_id, target_kind, pipeline_id, "
        "failure_reason, failure_detail, ts) VALUES (?, ?, ?, ?, ?, ?)",
        (gid, "Goal", "pid-prior", "lake_build_error",
         "error: L_main_sub_2.lean:13:41: expected token", db.now()),
    )
    conn.commit()

    captured = {}

    def fake_spawn(**kw):
        captured.update(kw)
        return 124

    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)

    pipeline.run_backward(
        conn, goal_id=gid, workspace=tmp_path,
        mfst=manifest.Manifest(problem="p", statement="True"),
        pipeline_id="pid-bw2",
    )
    assert captured["session_id"] == "saved-uuid"
    assert captured["is_retry"] is True
    assert "expected token" in (captured["retry_context"] or "")


def test_stale_session_falls_back_to_fresh_uuid(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """rc=125 (stale session) → mint fresh UUID, recompile context,
    cold-spawn once. Net effect: session is replaced, not cleared."""
    gid = _seed_root_goal(tmp_path, conn)
    db.set_backward_session_id(conn, gid, "stale-uuid")
    seen = []

    def fake_spawn(**kw):
        seen.append((kw["session_id"], kw["is_retry"]))
        # First call: stale; second call: also fail but with fresh sid
        return 125 if len(seen) == 1 else 124

    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)

    pipeline.run_backward(
        conn, goal_id=gid, workspace=tmp_path,
        mfst=manifest.Manifest(problem="p", statement="True"),
        pipeline_id="pid-bw-stale",
    )
    assert len(seen) == 2
    assert seen[0][0] == "stale-uuid"      # first try with saved sid
    assert seen[0][1] is True              # is_retry path
    assert seen[1][0] != "stale-uuid"      # fresh sid for cold restart
    assert seen[1][1] is False             # cold = is_retry False
    # rc=124 on the cold retry → session conservatively cleared
    assert db.get_backward_session_id(conn, gid) is None


def test_non_zero_non_timeout_keeps_session_id(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ordinary rc≠0 (not 124, not 125) → keep session for next
    dispatch's --resume."""
    gid = _seed_root_goal(tmp_path, conn)
    db.set_backward_session_id(conn, gid, "warm-uuid")
    monkeypatch.setattr(agent, "spawn_llm", lambda **kw: 1)

    pipeline.run_backward(
        conn, goal_id=gid, workspace=tmp_path,
        mfst=manifest.Manifest(problem="p", statement="True"),
        pipeline_id="pid-bw-fail",
    )
    assert db.get_backward_session_id(conn, gid) == "warm-uuid"
