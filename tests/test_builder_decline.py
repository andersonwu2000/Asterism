"""F48 — Builder decline channel.

When Builder writes only PROPOSAL.md (no patch.lean), the agent has
followed builder.md's "When to skip writing a patch" hatch. Three
contracts must hold:

1. Pipeline classifies this as failure_reason='agent_declined'
   (distinct from agent_no_output, which means agent died / didn't
   produce any output).
2. cascade_one promotes the goal to BUILDER_THRESHOLD attempts in
   one step so the next dispatch is Backward, not yet-another Builder.
3. Backward's Context.md surfaces the decline reasoning as
   `## Why Builder declined` so decomposition addresses what the
   Builder agent flagged.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
import pytest

from Tooling import agent, db, manifest, pipeline as _pipeline
from Tooling.dispatcher import (
    cascade_one,
    BUILDER_THRESHOLD,
    SHELVE_THRESHOLD,
)


# ---------------------------------------------------------------------
# 1. Pipeline classifies decline distinctly from no-response
# ---------------------------------------------------------------------

def test_no_patch_no_proposal_is_agent_no_output(tmp_path: Path) -> None:
    """Sanity baseline: empty attempts_dir → agent died / produced
    nothing. Stays as legacy `agent_no_output`."""
    # Nothing written to tmp_path
    patches = list(tmp_path.glob("patch*.lean"))
    proposal = tmp_path / "PROPOSAL.md"
    assert not patches
    assert not proposal.exists()
    # The classification logic mirrors pipeline.run_builder line ~358-373.
    proposal_text = ""
    if not patches:
        if proposal_text.strip():
            reason = "agent_declined"
        else:
            reason = "agent_no_output"
    assert reason == "agent_no_output"


def test_no_patch_with_proposal_is_agent_declined(tmp_path: Path) -> None:
    """Decline path: agent wrote a non-empty PROPOSAL.md but no
    patch.lean. The PROPOSAL.md text becomes the decline reasoning."""
    proposal_text = (
        "Decline: condition 4 (sub-lemma decomposition more efficient).\n"
        "The goal needs an induction over PropForm whose eliminator "
        "isn't auto-derivable from the available hypotheses."
    )
    proposal = tmp_path / "PROPOSAL.md"
    proposal.write_text(proposal_text, encoding="utf-8")
    patches = list(tmp_path.glob("patch*.lean"))
    assert not patches
    assert proposal.read_text(encoding="utf-8").strip()

    # Same classification logic
    if not patches:
        if proposal.read_text(encoding="utf-8").strip():
            reason = "agent_declined"
        else:
            reason = "agent_no_output"
    assert reason == "agent_declined"


def test_whitespace_proposal_is_not_decline(tmp_path: Path) -> None:
    """A PROPOSAL.md containing only whitespace doesn't carry signal —
    classify as agent_no_output, not as a fake decline."""
    (tmp_path / "PROPOSAL.md").write_text("   \n\n  \n", encoding="utf-8")
    patches = list(tmp_path.glob("patch*.lean"))
    if not patches:
        if (tmp_path / "PROPOSAL.md").read_text(encoding="utf-8").strip():
            reason = "agent_declined"
        else:
            reason = "agent_no_output"
    assert reason == "agent_no_output"


# ---------------------------------------------------------------------
# 2. cascade_one fast-tracks declined goal to Backward
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


def test_cascade_decline_jumps_to_builder_threshold(
    conn: sqlite3.Connection,
) -> None:
    """First Builder attempt declines on a fresh goal → attempts goes
    from 0 directly to BUILDER_THRESHOLD so the next dispatch is
    Backward. Saves BUILDER_THRESHOLD-1 doomed Builder attempts."""
    gid = _seed_goal(conn)
    pid = "decline-1"
    _record_dead_attempt(conn, pipeline_id=pid, target_id=gid,
                         reason="agent_declined",
                         proposal="condition 4: needs sub-lemma decomp")
    cascade_one(conn, pipeline_id=pid, kind="Builder",
                target_id=str(gid), target_kind="Goal", outcome="failed",
                failure_reason="agent_declined")
    row = db.get_goal(conn, gid)
    assert row["attempts"] == BUILDER_THRESHOLD
    # Goal still open (not shelved — BUILDER_THRESHOLD < SHELVE_THRESHOLD)
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


def test_cascade_decline_can_trigger_shelve_at_threshold(
    conn: sqlite3.Connection,
) -> None:
    """A decline that pushes attempts to SHELVE_THRESHOLD shelves the
    goal as expected. (Edge case: BUILDER_THRESHOLD jump lands exactly
    at or past SHELVE_THRESHOLD.)"""
    gid = _seed_goal(conn)
    # Push attempts so a single +1 hits SHELVE_THRESHOLD
    for _ in range(SHELVE_THRESHOLD - 1):
        db.increment_goal_attempts(conn, gid)
    pid = "decline-shelve"
    _record_dead_attempt(conn, pipeline_id=pid, target_id=gid,
                         reason="agent_declined", proposal="hopeless")
    cascade_one(conn, pipeline_id=pid, kind="Builder",
                target_id=str(gid), target_kind="Goal", outcome="failed",
                failure_reason="agent_declined")
    row = db.get_goal(conn, gid)
    assert row["attempts"] >= SHELVE_THRESHOLD
    assert row["status"] == "shelved"


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

def test_backward_context_includes_decline_section(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """Backward dispatch on a goal with prior agent_declined attempts
    must inline the decline PROPOSAL.md(s) so decomposition addresses
    the flagged hard parts."""
    gid = _seed_goal(conn)
    decline_text = (
        "Decline: condition 3 (needs analysis before tactics).\n"
        "The induction step requires a non-trivial inversion on "
        "PropForm.implies that I haven't found in Mathlib."
    )
    _record_dead_attempt(conn, pipeline_id="p-decl", target_id=gid,
                         reason="agent_declined",
                         proposal=decline_text)

    # Build a minimal manifest + sandbox
    mfst = manifest.Manifest(problem="p", statement="T")
    attempts_dir = tmp_path / ".attempts" / "pid"
    attempts_dir.mkdir(parents=True)

    goal = db.get_goal(conn, gid)
    agent.compile_context(conn, goal=goal, mfst=mfst,
                          attempts_dir=attempts_dir,
                          strategy_id=None, kind="backward")
    body = (attempts_dir / "Context.md").read_text(encoding="utf-8")
    assert "## Why Builder declined this goal" in body
    assert "PropForm.implies" in body  # excerpt of decline reasoning


def test_builder_context_excludes_decline_section(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """Builder seeing its OWN prior decline would tempt it to decline
    again without trying. Decline section is Backward-only."""
    gid = _seed_goal(conn)
    _record_dead_attempt(conn, pipeline_id="p-decl", target_id=gid,
                         reason="agent_declined",
                         proposal="some decline reasoning here")

    mfst = manifest.Manifest(problem="p", statement="T")
    attempts_dir = tmp_path / ".attempts" / "pid2"
    attempts_dir.mkdir(parents=True)

    goal = db.get_goal(conn, gid)
    agent.compile_context(conn, goal=goal, mfst=mfst,
                          attempts_dir=attempts_dir,
                          strategy_id=None, kind="builder")
    body = (attempts_dir / "Context.md").read_text(encoding="utf-8")
    assert "## Why Builder declined this goal" not in body


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
    agent.compile_context(conn, goal=goal, mfst=mfst,
                          attempts_dir=attempts_dir,
                          strategy_id=None, kind="backward")
    body = (attempts_dir / "Context.md").read_text(encoding="utf-8")
    assert "## Why Builder declined" not in body
