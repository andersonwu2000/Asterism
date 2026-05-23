"""F48 — Builder decline channel (cascade behavior).

When Builder produces a `-- decline: too_hard` directive in
patch.lean's leading comment block (Phase 6 single-output design),
the pipeline classifies the run as `failure_reason='agent_declined'`.
This file covers the cascade reaction to such a classification:

1. cascade_one promotes the goal to BUILDER_THRESHOLD attempts in
   one step so the next dispatch is Backward, not yet-another Builder.
2. Backward's Context.md surfaces the decline reasoning inline in
   the `### Direct attempts on this goal` umbrella sub-section so
   the next decomposition addresses what Builder flagged.

The directive-parsing classification itself is tested in
`tests/test_pipeline_pure.py` (`_extract_decline_reason`) and the
full pipeline branch in `tests/test_pipeline_builder.py`
(`test_run_builder_decline_returns_agent_declined`).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
import pytest

from Tooling import agent, pipeline as _pipeline
from Tooling.agent import context
from Tooling.state import db, manifest
from Tooling.core.dispatcher import (
    cascade_one,
    BUILDER_THRESHOLD,
    SHELVE_THRESHOLD,
)


# ---------------------------------------------------------------------
# cascade_one fast-tracks declined goal to Backward
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
                         proposal: str = "",
                         kind: str = "Builder") -> None:
    """pipelines + dead_attempts insert; FK requires the parent row."""
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
        (target_id, "Goal", pipeline_id, reason, "", proposal, db.now()),
    )
    conn.commit()


def test_cascade_decline_routes_to_backward_via_entry_kind(
    conn: sqlite3.Connection,
) -> None:
    """Phase 7 — Builder decline increments attempts by exactly 1 (the
    declining LLM call) and flips `entry_kind` to 'Backward' so the next
    dispatch routes to Backward. Pre-Phase-7 inflated attempts to
    BUILDER_THRESHOLD as a routing hack; that violated the 1:1 attempts
    ↔ dead_attempts invariant (decision 5/6) by counting attempts that
    never corresponded to LLM calls."""
    gid = _seed_goal(conn)
    pid = "decline-1"
    _record_dead_attempt(conn, pipeline_id=pid, target_id=gid,
                         reason="agent_declined",
                         proposal="condition 4: needs sub-lemma decomp")
    cascade_one(conn, pipeline_id=pid, kind="Builder",
                target_id=str(gid), target_kind="Goal", outcome="failed",
                failure_reason="agent_declined")
    row = db.get_goal(conn, gid)
    assert row["attempts"] == 1
    assert row["entry_kind"] == "Backward"
    # Goal still open (1 < SHELVE_THRESHOLD)
    assert row["status"] == "open"


def test_cascade_decline_at_high_attempts_still_increments_one(
    conn: sqlite3.Connection,
) -> None:
    """If a goal is already past BUILDER_THRESHOLD (e.g. multiple
    cascade events landed), a decline still costs +1 attempts toward
    SHELVE — the agent doesn't get to skip the SHELVE accountancy by
    declining repeatedly."""
    gid = _seed_goal(conn)
    # Manually push attempts to BUILDER_THRESHOLD + 1
    for _ in range(BUILDER_THRESHOLD + 1):
        db.increment_goal_attempts(conn, gid)
    starting = db.get_goal(conn, gid)["attempts"]
    pid = "decline-late"
    _record_dead_attempt(conn, pipeline_id=pid, target_id=gid,
                         reason="agent_declined",
                         proposal="still hard")
    cascade_one(conn, pipeline_id=pid, kind="Builder",
                target_id=str(gid), target_kind="Goal", outcome="failed",
                failure_reason="agent_declined")
    assert db.get_goal(conn, gid)["attempts"] == starting + 1


def test_cascade_decline_at_threshold_routes_to_pending_review(
    conn: sqlite3.Connection,
) -> None:
    """A decline that pushes attempts to SHELVE_THRESHOLD routes the
    goal to `pending_strategist_review` (B-1 fix, was: auto-shelve).
    Strategist decides ConfirmShelve / Reopen / Inject."""
    gid = _seed_goal(conn)
    for _ in range(SHELVE_THRESHOLD - 1):
        db.increment_goal_attempts(conn, gid)
    pid = "decline-pending"
    _record_dead_attempt(conn, pipeline_id=pid, target_id=gid,
                         reason="agent_declined", proposal="hopeless")
    cascade_one(conn, pipeline_id=pid, kind="Builder",
                target_id=str(gid), target_kind="Goal", outcome="failed",
                failure_reason="agent_declined")
    row = db.get_goal(conn, gid)
    assert row["attempts"] >= SHELVE_THRESHOLD
    assert row["status"] == "pending_strategist_review"


def test_cascade_normal_failure_unchanged_by_f48(
    conn: sqlite3.Connection,
) -> None:
    """Defense-in-depth: a real failure (lake_build_error / forbidden
    lemma / etc.) still increments by exactly +1, no jump."""
    gid = _seed_goal(conn)
    pid = "real-fail"
    _record_dead_attempt(conn, pipeline_id=pid, target_id=gid,
                         reason="lake_build_error")
    cascade_one(conn, pipeline_id=pid, kind="Builder",
                target_id=str(gid), target_kind="Goal", outcome="failed",
                failure_reason="lake_build_error")
    assert db.get_goal(conn, gid)["attempts"] == 1


# ---------------------------------------------------------------------
# 3. Backward Context.md surfaces decline reasoning
# ---------------------------------------------------------------------

def test_backward_context_surfaces_decline_in_direct_attempts(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """C3 — Builder declines no longer have their own
    `## Why Builder declined this goal` section; they appear inline
    in the umbrella's `### Direct attempts on this goal` sub-section
    as `agent_declined` rows. Backward dispatch must still see the
    decline PROPOSAL.md content (the decomposition signal)."""
    gid = _seed_goal(conn)
    decline_text = (
        "Decline: condition 3 (needs analysis before tactics).\n"
        "The induction step requires a non-trivial inversion on "
        "PropForm.implies that I haven't found in Mathlib."
    )
    _record_dead_attempt(conn, pipeline_id="p-decl", target_id=gid,
                         reason="agent_declined",
                         proposal=decline_text)

    mfst = manifest.Manifest(problem="p", statement="T")
    attempts_dir = tmp_path / ".attempts" / "pid"
    attempts_dir.mkdir(parents=True)

    goal = db.get_goal(conn, gid)
    context.compile_context(conn, goal=goal, mfst=mfst,
                          attempts_dir=attempts_dir,
                          strategy_id=None, kind="backward")
    body = (attempts_dir / "Context.md").read_text(encoding="utf-8")
    # Old top-level section gone
    assert "## Why Builder declined this goal" not in body
    # New: inline in the goal-history umbrella's direct_attempts sub
    assert "### Direct attempts on this goal" in body
    assert "agent_declined" in body
    assert "PropForm.implies" in body  # excerpt of decline reasoning
    # Lead-in note flagging the declined row to Backward
    assert "decomposition-needed" in body


def test_builder_context_also_sees_decline_history(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """C3 — `### Direct attempts on this goal` is now kind-agnostic
    (was Builder-only; the goal's failure history is its own
    property, not the pipeline's). In practice Builder rarely
    re-dispatches on a declined goal (cascade jumps attempts to
    BUILDER_THRESHOLD), so this test just verifies the rendering
    contract — declined rows surface for Builder kind too."""
    gid = _seed_goal(conn)
    _record_dead_attempt(conn, pipeline_id="p-decl", target_id=gid,
                         reason="agent_declined",
                         proposal="some decline reasoning here")

    mfst = manifest.Manifest(problem="p", statement="T")
    attempts_dir = tmp_path / ".attempts" / "pid2"
    attempts_dir.mkdir(parents=True)

    goal = db.get_goal(conn, gid)
    context.compile_context(conn, goal=goal, mfst=mfst,
                          attempts_dir=attempts_dir,
                          strategy_id=None, kind="builder")
    body = (attempts_dir / "Context.md").read_text(encoding="utf-8")
    # Old top-level section retired
    assert "## Why Builder declined this goal" not in body
    # New: declined row surfaces inside the goal-history umbrella for
    # Builder kind too (kind-gate retired in C3)
    assert "### Direct attempts on this goal" in body
    assert "agent_declined" in body


def test_decline_section_absent_when_no_declines(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """No prior declines on this goal → no decline section (must not
    leave an empty header dangling)."""
    gid = _seed_goal(conn)
    mfst = manifest.Manifest(problem="p", statement="T")
    attempts_dir = tmp_path / ".attempts" / "pid3"
    attempts_dir.mkdir(parents=True)

    goal = db.get_goal(conn, gid)
    context.compile_context(conn, goal=goal, mfst=mfst,
                          attempts_dir=attempts_dir,
                          strategy_id=None, kind="backward")
    body = (attempts_dir / "Context.md").read_text(encoding="utf-8")
    assert "## Why Builder declined" not in body
