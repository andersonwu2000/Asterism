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
        "INSERT INTO problems (name, manifest_path, created_at) "
        "VALUES (?, ?, ?)",
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

def test_cascade_infeasible_builder_shelves_goal_immediately(
    conn: sqlite3.Connection,
) -> None:
    """Infeasible Builder run shelves the goal directly (no further
    Builder/Backward attempts) so `_propagate_shelve` cascades the
    failure up to the parent strategy. Without this, the goal would
    consume SHELVE_THRESHOLD attempts on a provably-unprovable type.

    Phase 7 — attempts increments by exactly 1 (the infeasible LLM
    call DID happen) to preserve the 1:1 attempts ↔ dead_attempts
    invariant. The shelve happens regardless, so the +1 is cosmetic
    (already-terminal goals don't reuse attempts)."""
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
    assert row["status"] == "shelved"
    assert row["attempts"] == 1  # one LLM call counted (decision 5/6)


def test_cascade_infeasible_backward_shelves_goal_immediately(
    conn: sqlite3.Connection,
) -> None:
    """Mirror of the Builder branch: Backward agent escapes via the
    same channel. Shelve directly; attempts++ once preserves 1:1
    (Phase 7)."""
    gid = _seed_goal(conn)
    pid = "infeasible-bw"
    _record_dead_attempt(conn, pipeline_id=pid, target_id=gid,
                         reason="agent_infeasible", kind="Backward")
    cascade_one(conn, pipeline_id=pid, kind="Backward",
                target_id=str(gid), target_kind="Goal", outcome="failed",
                failure_reason="agent_infeasible")
    row = db.get_goal(conn, gid)
    assert row["status"] == "shelved"
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

    # Sub-goal shelved
    assert db.get_goal(conn, sub_gid)["status"] == "shelved"
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
    """Defense: `agent_declined` still routes to Backward — the
    infeasible branch must not intercept decline traffic. Phase 7 —
    routing now via `entry_kind='Backward'` instead of attempts
    inflation, attempts increments by 1 (the declining LLM call)."""
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
    assert row["entry_kind"] == "Backward"


# ---------------------------------------------------------------------
# 5. New decline directives (return_to_parent, shelve) — same cascade
#    semantics as agent_infeasible: shelve immediately + propagate up.
# ---------------------------------------------------------------------

def test_cascade_parent_needs_fix_shelves_goal(conn: sqlite3.Connection) -> None:
    """`return_to_parent` directive routes to failure_reason
    'parent_needs_fix' — semantically distinct from agent_infeasible
    (provable after parent fix vs unprovable in scope) but cascade
    behavior identical: shelve + propagate."""
    gid = _seed_goal(conn)
    pid = "rtp-1"
    _record_dead_attempt(conn, pipeline_id=pid, target_id=gid,
                         reason="parent_needs_fix")
    cascade_one(conn, pipeline_id=pid, kind="Builder",
                target_id=str(gid), target_kind="Goal", outcome="failed",
                failure_reason="parent_needs_fix")
    row = db.get_goal(conn, gid)
    assert row["status"] == "shelved"
    assert row["attempts"] == 1


def test_cascade_agent_shelved_shelves_goal(conn: sqlite3.Connection) -> None:
    """`shelve` directive routes to failure_reason 'agent_shelved' —
    cascades same as agent_infeasible / parent_needs_fix. Distinction
    is for downstream review (Strategist may revisit)."""
    gid = _seed_goal(conn)
    pid = "shelve-1"
    _record_dead_attempt(conn, pipeline_id=pid, target_id=gid,
                         reason="agent_shelved", kind="Backward")
    cascade_one(conn, pipeline_id=pid, kind="Backward",
                target_id=str(gid), target_kind="Goal", outcome="failed",
                failure_reason="agent_shelved")
    row = db.get_goal(conn, gid)
    assert row["status"] == "shelved"
    assert row["attempts"] == 1


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
