"""agent.compile_context — Context.md assembly from DB + Manifest."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from Tooling import db
from Tooling.agent import compile_context
from Tooling.manifest import Manifest


def _empty_manifest(name: str = "p") -> Manifest:
    return Manifest(problem=name, statement="T")


def _seed_problem_and_goal(conn: sqlite3.Connection, **goal_kw: object) -> int:
    conn.execute(
        "INSERT INTO problems (name, manifest_path, created_at) VALUES (?, ?, ?)",
        ("p", "Problems/p/Manifest.md", db.now()),
    )
    return db.insert_goal(
        conn, problem="p", slug="main", lean_path="Problems/p/Root.lean",
        statement="T", origin="root", difficulty=4, **goal_kw,
    )


def _record_pipeline(conn: sqlite3.Connection, pid: str, kind: str,
                     target_id: str, target_kind: str) -> None:
    conn.execute(
        "INSERT INTO pipelines (id, kind, target_id, target_kind, status,"
        " outcome, started_at, finished_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (pid, kind, target_id, target_kind, "failed", "failed",
         db.now(), db.now()),
    )
    conn.commit()


def test_context_includes_strategy_dead_attempts(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """Verify failures should surface in the parent goal's Context so a
    fresh Backward agent doesn't repeat the broken combination pattern."""
    gid = _seed_problem_and_goal(conn)
    sid = db.insert_strategy(
        conn, goal_id=gid, lean_path="Problems/p/Root.lean",
        created_by="pid-x",
        proposal_md="### My decomposition\n3 sub-goals via foo",
    )
    _record_pipeline(conn, "pid-x", "Verify", str(sid), "Strategy")
    db.record_dead_attempt(
        conn, target_id=sid, target_kind="Strategy", pipeline_id="pid-x",
        failure_reason="lake_build_error",
        failure_detail="error: type mismatch in have h_1",
    )

    goal = db.get_goal(conn, gid)
    out = compile_context(conn, goal=goal, mfst=_empty_manifest(),
                          attempts_dir=tmp_path)
    text = out.read_text(encoding="utf-8")

    assert "Past decompositions that failed Verify" in text
    assert "lake_build_error" in text
    assert "type mismatch" in text
    assert "My decomposition" in text


def test_context_no_strategy_section_when_clean(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    gid = _seed_problem_and_goal(conn)
    goal = db.get_goal(conn, gid)
    out = compile_context(conn, goal=goal, mfst=_empty_manifest(),
                          attempts_dir=tmp_path)
    text = out.read_text(encoding="utf-8")
    assert "Past decompositions that failed Verify" not in text


def test_context_subgoal_includes_parent_strategy(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """A backward-origin sub-goal should see its parent's slug, statement,
    and the originating strategy's PROPOSAL.md."""
    parent_gid = _seed_problem_and_goal(conn)
    sid = db.insert_strategy(
        conn, goal_id=parent_gid, lean_path="Problems/p/Root.lean",
        created_by="pid-y",
        proposal_md="parent decomposes into A, B, C",
    )
    sub_gid = db.insert_goal(
        conn, problem="p", slug="main_sub_1",
        lean_path="Problems/p/proofs/L_main_sub_1.lean",
        statement="A", origin="backward", difficulty=3, depth=1,
    )
    db.link_subgoal(conn, strategy_id=sid, subgoal_id=sub_gid, position=0)

    sub_goal = db.get_goal(conn, sub_gid)
    out = compile_context(conn, goal=sub_goal, mfst=_empty_manifest(),
                          attempts_dir=tmp_path)
    text = out.read_text(encoding="utf-8")
    assert "Parent goal & strategy" in text
    assert "main_sub_1" in text
    assert "main" in text  # parent slug
    assert "parent decomposes into A, B, C" in text
