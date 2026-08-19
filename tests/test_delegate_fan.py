"""A Delegate opens a fan, never a relay (owner ruling 2026-08-19).

A single sub-group buys zero concurrency over in-house AHEAD batches —
it is the parent's own pipeline stage wearing a fresh judgment loop
(the 2026-08-18 evidence: six single-child Delegates in 4.5h, every
author zero-own-brick, d7→d10). The count is on the RESULT (existing
active children + this batch's Delegates), so topping up a live fan
with one more line stays legal. Racing two groups on the same anchor
goal is explicitly legal OR-parallelism, and ownership routing over a
double anchor must be deterministic."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from Tooling.pipeline.strategist import Decision, verify_decisions
from Tooling.state import db as _db
from Tooling.state import groups as _groups

_PROMPTS = Path(__file__).resolve().parents[1] / "Tooling" / "prompts"

_BRIEF = (
    "# Charter\nSettle the toy claim series.\n"
    "## Why a project\nA clearly themed series of research items that "
    "cannot ride AHEAD.\n"
    "## Inheritance\nNothing yet.\n"
)


def _top(conn: sqlite3.Connection) -> int:
    conn.execute(
        "INSERT INTO problems (name, created_at) VALUES ('P', ?)",
        (_db.now(),))
    top = _groups.ensure_top_group(conn, "P", charter="Prove it.")
    conn.commit()
    return top


def _delegate() -> Decision:
    return Decision(kind="Delegate", brief=_BRIEF)


def test_a_fan_of_one_is_refused_with_the_way_out(
        conn: sqlite3.Connection) -> None:
    top = _top(conn)
    err = verify_decisions([_delegate()], conn, problem="P", group_id=top)
    assert "never a relay" in err
    assert "AHEAD" in err


def test_two_delegates_in_one_batch_pass_the_fan_check(
        conn: sqlite3.Connection) -> None:
    top = _top(conn)
    err = verify_decisions([_delegate(), _delegate()], conn,
                           problem="P", group_id=top)
    assert "never a relay" not in err
    assert err == ""


def test_topping_up_a_live_fan_with_one_line_is_legal(
        conn: sqlite3.Connection) -> None:
    top = _top(conn)
    _groups.open_group(conn, problem="P", parent_group_id=top,
                       charter="Existing live line.")
    conn.commit()
    err = verify_decisions([_delegate()], conn, problem="P", group_id=top)
    assert err == ""


def test_a_returned_sibling_does_not_count_toward_the_fan(
        conn: sqlite3.Connection) -> None:
    top = _top(conn)
    gid = _groups.open_group(conn, problem="P", parent_group_id=top,
                             charter="Line that came back.")
    _groups.set_status(conn, gid, "returned", event="test")
    conn.commit()
    err = verify_decisions([_delegate()], conn, problem="P", group_id=top)
    assert "never a relay" in err


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


def test_the_fan_sentence_is_mirrored_in_all_four_prompts() -> None:
    files = [
        _PROMPTS / "adversary" / "_contract.md",
        _PROMPTS / "strategist" / "routine.md",
        _PROMPTS / "strategist" / "pending_review.md",
        _PROMPTS / "strategist" / "inject_batch_done.md",
    ]
    for f in files:
        text = f.read_text(encoding="utf-8")
        assert "opens a FAN, never a relay" in text, f
        assert "Two groups may race one goal." in text, f
