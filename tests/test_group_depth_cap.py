"""The group tree caps two levels below the top (owner ruling
2026-08-19). Group depth partitions JUDGMENT, not mathematics — the
goal tree under any group stays unbounded — and past depth 2 the
observed behavior was pipeline-stage delegation under stacked
hypotheses: six Delegates in 4.5h (2026-08-18, all post-wording), every
author holding zero own bricks, two returned the same day, d7→d10.
Prose criteria ("why AHEAD cannot carry it") were argued past every
time; ancestry count cannot be.

Three pins: the verify gate (mechanical, names the way out), the
contract's availability sentence (judge and author read one text), and
the conditional Context affordance (a depth-2 group is TOLD the verb is
gone — an agent told about a verb a gate will refuse invents
workarounds)."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from Tooling.pipeline.strategist import Decision, verify_decision
from Tooling.state import db as _db
from Tooling.state import groups as _groups

_PROMPTS = Path(__file__).resolve().parents[1] / "Tooling" / "prompts"

_BRIEF = "Settle the toy claim — a kernel-checkable research item."
_REASON = "cannot prove in-house nor pace through AHEAD"


def _chain(conn: sqlite3.Connection) -> "tuple[int, int, int]":
    conn.execute(
        "INSERT INTO problems (name, created_at) VALUES ('P', ?)",
        (_db.now(),))
    top = _groups.ensure_top_group(conn, "P", charter="Prove it.")
    d1 = _groups.open_group(conn, problem="P", parent_group_id=top,
                            charter="Case A of the claim.")
    d2 = _groups.open_group(conn, problem="P", parent_group_id=d1,
                            charter="Sub-case A.1 of the claim.")
    conn.commit()
    return top, d1, d2


def test_depth_helper_counts_ancestry(conn: sqlite3.Connection) -> None:
    top, d1, d2 = _chain(conn)
    assert _groups.depth(conn, top) == 0
    assert _groups.depth(conn, d1) == 1
    assert _groups.depth(conn, d2) == 2
    assert _groups.GROUP_DEPTH_CAP == 2


def test_delegate_allowed_above_the_cap(conn: sqlite3.Connection) -> None:
    top, d1, _ = _chain(conn)
    for gid in (top, d1):
        err = verify_decision(
            Decision(kind="Delegate", brief=_BRIEF, reason=_REASON),
            conn, problem="P", group_id=gid)
        assert "unavailable at your depth" not in err, (gid, err)


def test_delegate_refused_at_the_cap_with_the_way_out(
        conn: sqlite3.Connection) -> None:
    _, _, d2 = _chain(conn)
    err = verify_decision(
        Decision(kind="Delegate", brief=_BRIEF, reason=_REASON),
        conn, problem="P", group_id=d2)
    assert "unavailable at your depth" in err
    # The gate names reachable actions, never a bare refusal.
    assert "AHEAD" in err
    assert "ReturnToParent(amend)" in err


def test_your_group_section_drops_the_verb_only_at_the_cap(
        conn: sqlite3.Connection) -> None:
    from Tooling.agent.phase2_context import _section_your_group
    _, d1, d2 = _chain(conn)
    at_d1 = "\n".join(_section_your_group(conn, "P", d1))
    at_d2 = "\n".join(_section_your_group(conn, "P", d2))
    assert "`Delegate` is not available at your depth" not in at_d1
    assert "`Delegate` is not available at your depth" in at_d2
    assert "AHEAD" in at_d2
