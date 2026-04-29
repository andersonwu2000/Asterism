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


def test_cascade_verify_failed_reopens_attempting_goal(
    conn: sqlite3.Connection,
) -> None:
    """After last live strategy dies, goal must return to 'open' so a fresh
    Backward can be dispatched. Otherwise goal is stuck 'attempting'."""
    gid = _seed_goal(conn)
    db.update_goal_status(conn, gid, "attempting")
    sid = _seed_strategy(conn, gid)
    cascade_one(conn, pipeline_id="pid", kind="Verify",
                target_id=str(sid), target_kind="Strategy", outcome="failed")
    g = db.get_goal(conn, gid)
    assert g["status"] == "open"


def test_cascade_verify_failed_keeps_attempting_when_other_strategies_live(
    conn: sqlite3.Connection,
) -> None:
    gid = _seed_goal(conn)
    db.update_goal_status(conn, gid, "attempting")
    sid1 = _seed_strategy(conn, gid)
    sid2 = db.insert_strategy(
        conn, goal_id=gid, lean_path=f"Problems/p/Root_{gid}.lean",
        created_by="pid",
    )
    cascade_one(conn, pipeline_id="pid", kind="Verify",
                target_id=str(sid1), target_kind="Strategy", outcome="failed")
    g = db.get_goal(conn, gid)
    assert g["status"] == "attempting"  # sid2 still live


# ---------------------------------------------------------------------
# OR parallelism (W5/C)
# ---------------------------------------------------------------------

def test_two_strategies_share_parent_lean_path(conn: sqlite3.Connection) -> None:
    """Drop of UNIQUE on strategies.lean_path: multiple strategies can
    coexist for the same parent goal."""
    gid = _seed_goal(conn)
    sid1 = db.insert_strategy(conn, goal_id=gid,
                              lean_path="Problems/p/Root.lean",
                              created_by="pid-1")
    sid2 = db.insert_strategy(conn, goal_id=gid,
                              lean_path="Problems/p/Root.lean",
                              created_by="pid-2")
    assert sid1 != sid2


def test_cascade_verify_proved_supersedes_siblings(
    conn: sqlite3.Connection,
) -> None:
    gid = _seed_goal(conn)
    sid_winner = db.insert_strategy(conn, goal_id=gid,
                                    lean_path="Problems/p/Root.lean",
                                    created_by="pid-w",
                                    scratch_path="proofs/_strategy_s1.lean")
    sid_loser1 = db.insert_strategy(conn, goal_id=gid,
                                    lean_path="Problems/p/Root.lean",
                                    created_by="pid-l1")
    sid_loser2 = db.insert_strategy(conn, goal_id=gid,
                                    lean_path="Problems/p/Root.lean",
                                    created_by="pid-l2")
    cascade_one(conn, pipeline_id="pid-w", kind="Verify",
                target_id=str(sid_winner), target_kind="Strategy",
                outcome="proved")
    statuses = {
        sid: conn.execute("SELECT status FROM strategies WHERE id = ?",
                          (sid,)).fetchone()["status"]
        for sid in (sid_winner, sid_loser1, sid_loser2)
    }
    assert statuses[sid_winner] == "succeeded"
    assert statuses[sid_loser1] == "superseded"
    assert statuses[sid_loser2] == "superseded"
    assert db.get_goal(conn, gid)["status"] == "proved"


def test_cascade_no_op_when_goal_already_proved(
    conn: sqlite3.Connection,
) -> None:
    """Late-arriving Builder/Backward result on a proved goal is silent."""
    gid = _seed_goal(conn)
    db.update_goal_status(conn, gid, "proved")
    cascade_one(conn, pipeline_id="late", kind="Builder",
                target_id=str(gid), target_kind="Goal", outcome="failed")
    g = db.get_goal(conn, gid)
    assert g["status"] == "proved"  # not touched
    assert g["attempts"] == 0       # not incremented


def test_cascade_no_op_when_strategy_superseded(
    conn: sqlite3.Connection,
) -> None:
    gid = _seed_goal(conn)
    sid = db.insert_strategy(conn, goal_id=gid,
                             lean_path="Problems/p/Root.lean",
                             created_by="pid")
    db.update_strategy_status(conn, sid, "superseded")
    cascade_one(conn, pipeline_id="late", kind="Verify",
                target_id=str(sid), target_kind="Strategy", outcome="proved")
    s = conn.execute("SELECT status FROM strategies WHERE id = ?",
                     (sid,)).fetchone()
    assert s["status"] == "superseded"  # cascade did not flip to succeeded


def test_open_goals_filters_orphan_subgoals(conn: sqlite3.Connection) -> None:
    """A backward-origin sub-goal whose parent strategy is 'superseded'
    must be excluded from open_goals."""
    parent_gid = _seed_goal(conn)
    sid = db.insert_strategy(conn, goal_id=parent_gid,
                             lean_path="Problems/p/Root.lean",
                             created_by="pid")
    sub_gid = db.insert_goal(
        conn, problem="p", slug="orphan_sub",
        lean_path="Problems/p/proofs/L_orphan_sub.lean",
        statement="T", origin="backward", difficulty=3, depth=1,
    )
    db.link_subgoal(conn, strategy_id=sid, subgoal_id=sub_gid, position=0)

    # Initially: parent strategy alive → sub-goal eligible
    ids = [g["id"] for g in db.open_goals(conn)]
    assert sub_gid in ids

    # Mark strategy superseded → sub-goal becomes orphan
    db.update_strategy_status(conn, sid, "superseded")
    ids = [g["id"] for g in db.open_goals(conn)]
    assert sub_gid not in ids
    assert parent_gid in ids  # root unaffected


def test_queue_count_helper(conn: sqlite3.Connection) -> None:
    db.enqueue(conn, kind="Backward", target_id="42")
    db.enqueue(conn, kind="Backward", target_id="42")
    db.enqueue(conn, kind="Builder", target_id="42")
    assert db.queue_count(conn, target_id="42", kind="Backward") == 2
    assert db.queue_count(conn, target_id="42", kind="Builder") == 1
    assert db.queue_count(conn, target_id="99", kind="Backward") == 0


def test_bfs_refill_or_fanout_for_backward(conn: sqlite3.Connection) -> None:
    """For an open goal whose next worker is Backward, bfs_refill must
    enqueue up to or_fanout entries (running set empty here)."""
    from Tooling.dispatcher import bfs_refill
    gid = _seed_goal(conn, difficulty=4)  # difficulty>=4 → Backward
    bfs_refill(conn, running=set(), or_fanout=3)
    assert db.queue_count(conn, target_id=str(gid), kind="Backward") == 3


def test_bfs_refill_builder_capped_at_one(conn: sqlite3.Connection) -> None:
    """Builder is single-attempt-per-goal even with high fanout."""
    from Tooling.dispatcher import bfs_refill
    gid = _seed_goal(conn, difficulty=2)  # difficulty<4, attempts=0 → Builder
    bfs_refill(conn, running=set(), or_fanout=5)
    assert db.queue_count(conn, target_id=str(gid), kind="Builder") == 1


def test_strategies_ready_for_verify_excludes_proved_goal(
    conn: sqlite3.Connection,
) -> None:
    """W6 fix: a strategy whose own goal is already proved (by sibling
    OR strategy) must NOT be returned as ready, even if its sub-goals
    are all proved. Prevents the Verify-thrashing loop seen in
    compactness smoke."""
    gid = _seed_goal(conn)
    sid = db.insert_strategy(conn, goal_id=gid,
                             lean_path="Problems/p/Root.lean",
                             created_by="pid")
    # Add a proved sub-goal so the EXISTS clause is satisfied.
    sub_gid = db.insert_goal(
        conn, problem="p", slug="proved_sub",
        lean_path="Problems/p/proofs/L_proved_sub.lean",
        statement="T", origin="backward", difficulty=1, depth=1,
    )
    db.update_goal_status(conn, sub_gid, "proved")
    db.link_subgoal(conn, strategy_id=sid, subgoal_id=sub_gid, position=0)

    # While goal is open: ready
    assert any(s["id"] == sid for s in db.strategies_ready_for_verify(conn))

    # Once goal is proved (by sibling): NOT ready
    db.update_goal_status(conn, gid, "proved")
    assert not any(s["id"] == sid for s in db.strategies_ready_for_verify(conn))


def test_cascade_finalizes_superseded_when_goal_already_proved(
    conn: sqlite3.Connection,
) -> None:
    """W6 fix: cascade no-op entry should ALSO transition a still-'proposed'
    strategy to 'superseded' when its goal is already proved. Without
    this, the strategy stays 'proposed' and bfs_refill thrashes."""
    gid = _seed_goal(conn)
    db.update_goal_status(conn, gid, "proved")
    sid = db.insert_strategy(conn, goal_id=gid,
                             lean_path="Problems/p/Root.lean",
                             created_by="pid")
    cascade_one(conn, pipeline_id="late", kind="Verify",
                target_id=str(sid), target_kind="Strategy", outcome="failed")
    s = conn.execute("SELECT status FROM strategies WHERE id = ?",
                     (sid,)).fetchone()
    assert s["status"] == "superseded"
