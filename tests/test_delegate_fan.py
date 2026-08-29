"""A batch delegates several groups or none — never exactly one (owner
ruling 2026-08-19, tightened the same day from the active-children
count: as long as one line was already in flight, per-batch top-ups let
a group keep shirking one Delegate at a time).

The evidence: six single-child Delegates in 4.5h (2026-08-18, all
post-wording), every author zero-own-brick, two returned the same day,
d7→d10 — pipeline stages wearing fresh judgment loops. The count is
per BATCH and only per batch; racing two groups on the same anchor
goal is explicitly legal OR-parallelism, and ownership routing over a
double anchor must be deterministic."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from Tooling.pipeline.strategist import Decision, verify_decisions
from Tooling.state import db as _db
from Tooling.state import groups as _groups

_PROMPTS = Path(__file__).resolve().parents[1] / "Tooling" / "prompts"


def _top(conn: sqlite3.Connection) -> int:
    conn.execute(
        "INSERT INTO problems (name, created_at) VALUES ('P', ?)",
        (_db.now(),))
    top = _groups.ensure_top_group(conn, "P", charter="Prove it.")
    conn.commit()
    return top


def _delegate(claim: str = "case A") -> Decision:
    return Decision(kind="Delegate",
                    brief=f"Settle {claim} — a kernel-checkable item.",
                    reason="cannot prove in-house nor pace through AHEAD")


def test_a_lone_delegate_is_refused_with_the_way_out(
        conn: sqlite3.Connection) -> None:
    top = _top(conn)
    err = verify_decisions([_delegate()], conn, problem="P", group_id=top)
    assert "never exactly one" in err
    assert "AHEAD" in err


def test_two_delegates_in_one_batch_pass(
        conn: sqlite3.Connection) -> None:
    top = _top(conn)
    err = verify_decisions([_delegate("case A"), _delegate("case B")],
                           conn, problem="P", group_id=top)
    assert err == ""


def test_an_existing_live_fan_does_not_excuse_a_lone_delegate(
        conn: sqlite3.Connection) -> None:
    """The tightening's whole point: with the old active-children
    count, one line in flight let a group top up one group at a time
    forever — serial relay under a fan-shaped alibi."""
    top = _top(conn)
    _groups.open_group(conn, problem="P", parent_group_id=top,
                       charter="Existing live line.")
    conn.commit()
    err = verify_decisions([_delegate()], conn, problem="P", group_id=top)
    assert "never exactly one" in err


def test_a_batch_with_no_delegates_is_untouched(
        conn: sqlite3.Connection) -> None:
    top = _top(conn)
    err = verify_decisions(
        [Decision(kind="Noop", reason="work in flight")],
        conn, problem="P", group_id=top)
    assert "never exactly one" not in err


def test_two_groups_may_race_one_goal_and_routing_is_deterministic(
        conn: sqlite3.Connection) -> None:
    top = _top(conn)
    goal = _db.insert_goal(conn, problem="P", slug="hard_one",
                           lean_path="P/L_hard_one.lean", statement="S",
                           origin="backward")
    a = _groups.open_group(conn, problem="P", parent_group_id=top,
                           charter="Attack via route A.",
                           anchor_goal_id=goal)
    b = _groups.open_group(conn, problem="P", parent_group_id=top,
                           charter="Attack via route B.",
                           anchor_goal_id=goal)
    conn.commit()
    assert a != b
    # Newest racer wins shared-subtree routing — pinned, because an
    # unordered tie under LIMIT 1 routes reviews arbitrarily.
    owner = _groups.group_for_goal(conn, "P", goal)
    assert owner is not None and int(owner["id"]) == max(a, b)


