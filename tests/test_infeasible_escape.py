"""Infeasibility escape channel.

When Builder or Backward emits a `-- decline: parent_type_infeasible`
directive at the top of patch.lean (Phase 6 single-output design), the
agent has constructed a counterexample showing the goal type is
unprovable. The framework must:

1. Parse the directive from the leading comment block (covered by
   `test_pipeline_pure.py:test_extract_decline_*`).
2. Classify the run as `failure_reason='agent_infeasible'` (distinct
   from `agent_declined`, which routes the same goal to Backward;
   infeasible cascades up to redesign the parent strategy).
3. cascade_one shelves the goal directly (skip attempts++) and calls
   `_propagate_shelve` so the parent strategy dies and the parent goal
   re-opens for fresh Backward decomposition.

This file covers (2)+(3) — the cascade behavior given a pre-classified
`agent_infeasible` failure_reason.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from Tooling.state import db
from Tooling.core.dispatcher import cascade_one


# ---------------------------------------------------------------------
# Cascade behavior given `failure_reason='agent_infeasible'`
# ---------------------------------------------------------------------

def _seed_goal(conn: sqlite3.Connection, *, problem: str = "p") -> int:
    conn.execute(
        "INSERT INTO problems (name, manifest_path, created_at, bootstrap_done) "
        "VALUES (?, ?, ?, 1)",
        (problem, "Problems/p/Manifest.md", db.now()),
    )
    return db.insert_goal(
        conn, problem=problem, slug="main",
        lean_path="Problems/p/Root.lean",
        statement="T", origin="root",
    )


def _record_dead_attempt(conn: sqlite3.Connection, *, pipeline_id: str,
                         target_id: int, reason: str,
                         kind: str = "Builder") -> None:
    conn.execute(
        "INSERT INTO pipelines (id, kind, target_id, target_kind, "
        "status, outcome, started_at, finished_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (pipeline_id, kind, str(target_id), "Goal", "failed", "failed",
         db.now(), db.now()),
    )
    conn.execute(
        "INSERT INTO dead_attempts (target_id, target_kind, pipeline_id, "
        "failure_reason, failure_detail, proposal_md, ts) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (target_id, "Goal", pipeline_id, reason, "", "", db.now()),
    )
    conn.commit()


# ---------------------------------------------------------------------
# 2. cascade_one shelves the goal + skips attempts++ on infeasible
# ---------------------------------------------------------------------

def test_cascade_infeasible_builder_disproves_goal_immediately(
    conn: sqlite3.Connection,
) -> None:
    """Infeasible Builder run marks the goal `disproved` (hard terminal,
    agent gave counterexample) so `_propagate_shelve` cascades up to
    the parent strategy. Without this, the goal would consume
    SHELVE_THRESHOLD attempts on a provably-unprovable type.

    Phase 2 — status changed from 'shelved' to 'disproved' (status
    enum split by decline directive; see docs/archive/design/phase2/pipelines.md
    §4.2 Rule 1). attempts increments by exactly 1 to preserve the
    1:1 attempts ↔ dead_attempts invariant."""
    gid = _seed_goal(conn)
    pid = "infeasible-1"
    _record_dead_attempt(conn, pipeline_id=pid, target_id=gid,
                         reason="agent_infeasible")
    pre = db.get_goal(conn, gid)
    assert pre["attempts"] == 0
    cascade_one(conn, pipeline_id=pid, kind="Builder",
                target_id=str(gid), target_kind="Goal", outcome="failed",
                failure_reason="agent_infeasible")
    row = db.get_goal(conn, gid)
    assert row["status"] == "disproved"
    assert row["attempts"] == 1  # one LLM call counted


def test_cascade_infeasible_backward_disproves_goal_immediately(
    conn: sqlite3.Connection,
) -> None:
    """Mirror of the Builder branch: Backward agent escapes via the
    same channel. Phase 2 — status is 'disproved'; attempts++ once."""
    gid = _seed_goal(conn)
    pid = "infeasible-bw"
    _record_dead_attempt(conn, pipeline_id=pid, target_id=gid,
                         reason="agent_infeasible", kind="Backward")
    cascade_one(conn, pipeline_id=pid, kind="Backward",
                target_id=str(gid), target_kind="Goal", outcome="failed",
                failure_reason="agent_infeasible")
    row = db.get_goal(conn, gid)
    assert row["status"] == "disproved"
    assert row["attempts"] == 1


def test_cascade_infeasible_propagates_to_parent_strategy(
    conn: sqlite3.Connection,
) -> None:
    """End-to-end: a Backward strategy created sub-goal G_sub. Builder
    on G_sub returns infeasible. _propagate_shelve must kill the parent
    strategy and re-open the parent goal so a fresh Backward redesigns."""
    parent_gid = _seed_goal(conn)
    # Create a Backward strategy on the parent and a sub-goal
    cur = conn.execute(
        "INSERT INTO strategies (goal_id, lean_path, scratch_path, "
        "status, proposal_md, created_by, created_at) "
        "VALUES (?, ?, ?, 'proposed', '', 'test', ?)",
        (parent_gid, "Problems/p/proofs/L_main.lean",
         "Problems/p/proofs/_strategy_s1.lean", db.now()),
    )
    sid = cur.lastrowid
    sub_gid = db.insert_goal(
        conn, problem="p", slug="s1_sub_1",
        lean_path="Problems/p/proofs/L_s1_sub_1.lean",
        statement="T", origin="backward",
    )
    conn.execute(
        "INSERT INTO strategy_subgoals (strategy_id, subgoal_id, position) "
        "VALUES (?, ?, 0)",
        (sid, sub_gid),
    )
    # Parent goal moves to 'attempting' as soon as the strategy is
    # registered (matches dispatcher's Backward-success branch).
    db.update_goal_status(conn, parent_gid, "attempting")
    conn.commit()

    pid = "infeasible-prop"
    _record_dead_attempt(conn, pipeline_id=pid, target_id=sub_gid,
                         reason="agent_infeasible")
    cascade_one(conn, pipeline_id=pid, kind="Builder",
                target_id=str(sub_gid), target_kind="Goal",
                outcome="failed", failure_reason="agent_infeasible")

    # Sub-goal disproved (Phase 2 — was 'shelved' pre-split)
    assert db.get_goal(conn, sub_gid)["status"] == "disproved"
    # Parent strategy killed
    s_status = conn.execute(
        "SELECT status FROM strategies WHERE id=?", (sid,)
    ).fetchone()[0]
    assert s_status == "dead"
    # Parent goal re-opened (no other live strategy)
    assert db.get_goal(conn, parent_gid)["status"] == "open"


# ---------------------------------------------------------------------
# 4. agent_declined still works (didn't accidentally hijack F48)
# ---------------------------------------------------------------------

def test_cascade_decline_path_unaffected(conn: sqlite3.Connection) -> None:
    """Defense: the infeasible branch must not intercept decline
    traffic — `agent_declined` counts one attempt (the declining LLM
    call) and leaves the goal open (entry_kind routing retired v33)."""
    gid = _seed_goal(conn)
    pid = "decline-1"
    _record_dead_attempt(conn, pipeline_id=pid, target_id=gid,
                         reason="agent_declined")
    cascade_one(conn, pipeline_id=pid, kind="Builder",
                target_id=str(gid), target_kind="Goal", outcome="failed",
                failure_reason="agent_declined")
    row = db.get_goal(conn, gid)
    assert row["status"] == "open"  # NOT shelved
    assert row["attempts"] == 1


# ---------------------------------------------------------------------
# 5. New decline directives (return_to_parent, shelve) — same cascade
#    semantics as agent_infeasible: shelve immediately + propagate up.
# ---------------------------------------------------------------------

def test_cascade_parent_needs_fix_marks_goal_dead(conn: sqlite3.Connection) -> None:
    """Phase 6: `return_to_parent` directive routes to failure_reason
    'parent_needs_fix' which flips the goal to status='dead' (the
    parent strategy was wrong, this goal is moot in that context).
    Distinct from 'shelved' (reopenable, soft) and 'disproved'
    (counterexample, dedupe blocks). Same upward-kill cascade as
    disproved so the parent goal retries with a different decomposition."""
    gid = _seed_goal(conn)
    pid = "rtp-1"
    _record_dead_attempt(conn, pipeline_id=pid, target_id=gid,
                         reason="parent_needs_fix")
    cascade_one(conn, pipeline_id=pid, kind="Builder",
                target_id=str(gid), target_kind="Goal", outcome="failed",
                failure_reason="parent_needs_fix")
    row = db.get_goal(conn, gid)
    assert row["status"] == "dead"
    assert row["attempts"] == 1


def test_cascade_agent_shelved_routes_to_strategist_review(
    conn: sqlite3.Connection,
) -> None:
    """Phase 2 — `shelve` directive routes goal to
    'pending_strategist_review' (transitional, not terminal) and
    enqueues a problem-keyed Strategist run (Phase 6). No
    _propagate_shelve; upstream strategy chain stays alive until
    Strategist commits ConfirmShelve / Reopen / Inject."""
    gid = _seed_goal(conn)
    pid = "shelve-1"
    _record_dead_attempt(conn, pipeline_id=pid, target_id=gid,
                         reason="agent_shelved", kind="Backward")
    cascade_one(conn, pipeline_id=pid, kind="Backward",
                target_id=str(gid), target_kind="Goal", outcome="failed",
                failure_reason="agent_shelved")
    row = db.get_goal(conn, gid)
    assert row["status"] == "pending_strategist_review"
    assert row["attempts"] == 1
    # Strategist enqueued group-keyed (v35: the seat belongs to the group
    # that owns the goal — here the problem's top group).
    from Tooling.state import groups as _g
    q = conn.execute(
        "SELECT kind, target_id, target_kind, problem FROM queue"
        " WHERE kind='Strategist'"
    ).fetchall()
    assert len(q) == 1
    assert q[0]["target_id"] == str(_g.top_group(conn, "p")["id"])
    assert q[0]["target_kind"] == "Group"
    assert q[0]["problem"] == "p"


# ---------------------------------------------------------------------
# 6. Parser → failure_reason mapping (the four decline directives map
#    to the four failure_reason values via DECLINE_TO_FAILURE_REASON).
# ---------------------------------------------------------------------

def test_decline_directive_to_failure_reason_mapping() -> None:
    from Tooling.pipeline import (
        DECLINE_TO_FAILURE_REASON, DECLINE_UNPROVABLE,
        DECLINE_RETURN_TO_PARENT, DECLINE_SHELVE,
        DECLINE_NEEDS_DECOMPOSITION,
    )
    assert DECLINE_TO_FAILURE_REASON[DECLINE_UNPROVABLE] == "agent_infeasible"
    assert DECLINE_TO_FAILURE_REASON[DECLINE_RETURN_TO_PARENT] == "parent_needs_fix"
    assert DECLINE_TO_FAILURE_REASON[DECLINE_SHELVE] == "agent_shelved"
    assert DECLINE_TO_FAILURE_REASON[DECLINE_NEEDS_DECOMPOSITION] == "agent_declined"
