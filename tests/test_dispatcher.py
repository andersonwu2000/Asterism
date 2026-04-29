"""dispatcher.next_worker_kind + cascade_one state transitions."""
from __future__ import annotations

import sqlite3

import pytest

from Tooling import db
from Tooling.dispatcher import next_worker_kind, cascade_one, SHELVE_THRESHOLD


# ---------------------------------------------------------------------
# next_worker_kind
# ---------------------------------------------------------------------

def _fake_goal(*, difficulty: int, attempts: int) -> dict:
    return {"difficulty": difficulty, "attempts": attempts}


def test_next_worker_kind_high_difficulty() -> None:
    assert next_worker_kind(_fake_goal(difficulty=5, attempts=0)) == "Backward"
    assert next_worker_kind(_fake_goal(difficulty=4, attempts=0)) == "Backward"


def test_next_worker_kind_easy_first_attempts() -> None:
    assert next_worker_kind(_fake_goal(difficulty=2, attempts=0)) == "Builder"
    assert next_worker_kind(_fake_goal(difficulty=1, attempts=2)) == "Builder"


def test_next_worker_kind_easy_after_two_attempts() -> None:
    assert next_worker_kind(_fake_goal(difficulty=2, attempts=3)) == "Backward"


# ---------------------------------------------------------------------
# cascade_one — Builder
# ---------------------------------------------------------------------

def _seed_goal(conn: sqlite3.Connection, *, problem: str = "p",
               difficulty: int = 2) -> int:
    conn.execute(
        "INSERT INTO problems (name, manifest_path, created_at) VALUES (?, ?, ?)",
        (problem, "Problems/p/Manifest.md", db.now()),
    )
    return db.insert_goal(
        conn, problem=problem, slug="main", lean_path="Problems/p/Root.lean",
        statement="T", origin="root", difficulty=difficulty,
    )


def test_cascade_builder_proved(conn: sqlite3.Connection) -> None:
    gid = _seed_goal(conn)
    cascade_one(conn, pipeline_id="pid", kind="Builder",
                target_id=str(gid), target_kind="Goal", outcome="proved")
    row = db.get_goal(conn, gid)
    assert row["status"] == "proved"


def test_cascade_builder_failed_increments_attempts(conn: sqlite3.Connection) -> None:
    gid = _seed_goal(conn)
    cascade_one(conn, pipeline_id="pid", kind="Builder",
                target_id=str(gid), target_kind="Goal", outcome="failed")
    row = db.get_goal(conn, gid)
    assert row["attempts"] == 1
    assert row["status"] == "open"


def test_cascade_builder_shelves_at_threshold(conn: sqlite3.Connection) -> None:
    gid = _seed_goal(conn)
    for _ in range(SHELVE_THRESHOLD):
        cascade_one(conn, pipeline_id="pid", kind="Builder",
                    target_id=str(gid), target_kind="Goal", outcome="failed")
    row = db.get_goal(conn, gid)
    assert row["status"] == "shelved"
    assert row["attempts"] == SHELVE_THRESHOLD


# ---------------------------------------------------------------------
# cascade_one — Backward
# ---------------------------------------------------------------------

def test_cascade_backward_success_marks_attempting(conn: sqlite3.Connection) -> None:
    gid = _seed_goal(conn)
    cascade_one(conn, pipeline_id="pid", kind="Backward",
                target_id=str(gid), target_kind="Goal", outcome="success")
    row = db.get_goal(conn, gid)
    assert row["status"] == "attempting"


def test_cascade_backward_failed_increments(conn: sqlite3.Connection) -> None:
    gid = _seed_goal(conn)
    cascade_one(conn, pipeline_id="pid", kind="Backward",
                target_id=str(gid), target_kind="Goal", outcome="failed")
    row = db.get_goal(conn, gid)
    assert row["attempts"] == 1


# ---------------------------------------------------------------------
# cascade_one — Verify
# ---------------------------------------------------------------------

def _seed_strategy(conn: sqlite3.Connection, goal_id: int) -> int:
    return db.insert_strategy(
        conn, goal_id=goal_id, lean_path=f"Problems/p/Root_{goal_id}.lean",
        created_by="pid",
    )


def test_cascade_verify_proved_succeeds_strategy_and_goal(
    conn: sqlite3.Connection,
) -> None:
    gid = _seed_goal(conn)
    sid = _seed_strategy(conn, gid)
    cascade_one(conn, pipeline_id="pid", kind="Verify",
                target_id=str(sid), target_kind="Strategy", outcome="proved")
    s = conn.execute("SELECT status FROM strategies WHERE id = ?", (sid,)).fetchone()
    g = db.get_goal(conn, gid)
    assert s["status"] == "succeeded"
    assert g["status"] == "proved"


def test_cascade_verify_failed_marks_strategy_dead(
    conn: sqlite3.Connection,
) -> None:
    gid = _seed_goal(conn)
    sid = _seed_strategy(conn, gid)
    cascade_one(conn, pipeline_id="pid", kind="Verify",
                target_id=str(sid), target_kind="Strategy", outcome="failed")
    s = conn.execute("SELECT status FROM strategies WHERE id = ?", (sid,)).fetchone()
    g = db.get_goal(conn, gid)
    assert s["status"] == "dead"
    assert g["attempts"] == 1
