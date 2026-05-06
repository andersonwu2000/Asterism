"""Infeasibility escape channel.

When Builder or Backward writes only PROPOSAL.md with frontmatter
`decline_reason: parent_type_infeasible`, the agent has constructed a
counterexample showing the parent's sub-goal type is unprovable. The
framework must:

1. Parse `decline_reason` from PROPOSAL.md frontmatter.
2. Classify the run as `failure_reason='agent_infeasible'`
   (distinct from `agent_declined`, which routes the same goal to
   Backward; infeasible cascades up to redesign the parent strategy).
3. cascade_one shelves the goal directly (skip attempts++) and calls
   `_propagate_shelve` so the parent strategy dies and the parent goal
   re-opens for fresh Backward decomposition.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from Tooling import db
from Tooling.dispatcher import cascade_one
from Tooling.pipeline import (
    DECLINE_PARENT_TYPE_INFEASIBLE,
    DECLINE_TOO_HARD,
    _parse_decline_reason,
)


# ---------------------------------------------------------------------
# 1. Frontmatter parser
# ---------------------------------------------------------------------

def test_parse_decline_reason_returns_value() -> None:
    text = (
        "---\n"
        "decline_reason: parent_type_infeasible\n"
        "---\n"
        "## Counterexample\n"
        "s=(0,0), q=(2,0), r=(5,0), p=(0,3) ...\n"
    )
    assert _parse_decline_reason(text) == DECLINE_PARENT_TYPE_INFEASIBLE


def test_parse_decline_reason_too_hard() -> None:
    text = (
        "---\n"
        "decline_reason: too_hard\n"
        "---\n"
        "Need a Mathlib lemma about ...\n"
    )
    assert _parse_decline_reason(text) == DECLINE_TOO_HARD


def test_parse_decline_reason_returns_none_when_missing() -> None:
    assert _parse_decline_reason("just prose, no frontmatter") is None


def test_parse_decline_reason_returns_none_when_no_field() -> None:
    text = "---\nfoo: bar\n---\nbody"
    assert _parse_decline_reason(text) is None


def test_parse_decline_reason_tolerates_extra_fields() -> None:
    text = (
        "---\n"
        "author: claude\n"
        "decline_reason: parent_type_infeasible\n"
        "tag: kelly\n"
        "---\n"
    )
    assert _parse_decline_reason(text) == DECLINE_PARENT_TYPE_INFEASIBLE


# ---------------------------------------------------------------------
# 2. _is_agent_infeasible helper
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
    """Infeasible Builder run shelves the goal in one shot (no attempts
    burn) so `_propagate_shelve` cascades the failure up to the parent
    strategy. Without this, the goal would consume SHELVE_THRESHOLD
    Builder attempts on a provably-unprovable type."""
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
    assert row["attempts"] == 0  # no increment


def test_cascade_infeasible_backward_shelves_goal_immediately(
    conn: sqlite3.Connection,
) -> None:
    """Mirror of the Builder branch: Backward agent escapes via the
    same channel. Shelve directly, no attempts burn."""
    gid = _seed_goal(conn)
    pid = "infeasible-bw"
    _record_dead_attempt(conn, pipeline_id=pid, target_id=gid,
                         reason="agent_infeasible", kind="Backward")
    cascade_one(conn, pipeline_id=pid, kind="Backward",
                target_id=str(gid), target_kind="Goal", outcome="failed",
                failure_reason="agent_infeasible")
    row = db.get_goal(conn, gid)
    assert row["status"] == "shelved"
    assert row["attempts"] == 0


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
    """Defense: F48 `agent_declined` still jumps to BUILDER_THRESHOLD
    (same-goal Backward) — the new infeasible branch must not intercept
    decline traffic."""
    from Tooling.dispatcher import BUILDER_THRESHOLD
    gid = _seed_goal(conn)
    pid = "decline-1"
    _record_dead_attempt(conn, pipeline_id=pid, target_id=gid,
                         reason="agent_declined")
    cascade_one(conn, pipeline_id=pid, kind="Builder",
                target_id=str(gid), target_kind="Goal", outcome="failed",
                failure_reason="agent_declined")
    row = db.get_goal(conn, gid)
    assert row["status"] == "open"  # NOT shelved
    assert row["attempts"] == BUILDER_THRESHOLD
