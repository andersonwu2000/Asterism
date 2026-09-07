"""Context.md described g10941 both ways in one file (2026-09-07 12:25).

Lines 301-302 said the Inject was PARKED with no worker and no wake
coming; lines 426-428 listed the same goal as a dispatched line still
running. Two renderers, two sources for one question: `## Lines in
flight` gated on the produced goal's STATUS, the decision replay on
whether work is actually moving. An `attempting` goal with nothing
under it and no worker satisfies the first and fails the second, and
an Adversary reported the pair mid-round.

One predicate now answers it for both — and it ANNOTATES the audit's
roster rather than filtering it: a line nobody is working is exactly
what criteria 3 and 4 exist to rule on.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from Tooling.state import db
from Tooling.state import groups as groups_store


# --------------------------------------- one predicate, two surfaces

@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    c = db.connect(tmp_path / "a.db")
    db.init_schema(c)
    c.execute("INSERT INTO problems (name, created_at, bootstrap_done)"
              " VALUES ('p', ?, 1)", (db.now(),))
    c.commit()
    return c


def _p_goal(conn, slug, status="open", depth=0):
    return db.insert_goal(conn, problem="p", slug=slug,
                          lean_path=f"Problems/p/proofs/L_{slug}.lean",
                          statement=f"theorem {slug} : T", origin="backward",
                          depth=depth, status=status)


def _p_inject(conn, group_id, root_id, batch="b1"):
    conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, batch_id, group_id,"
        " produced_goal_id, outcome, created_at, updated_at)"
        " VALUES ('p', 0, 'inject_batch_done', 'Inject', ?, ?, ?, NULL,"
        " ?, ?)", (batch, group_id, root_id, db.now(), db.now()))
    conn.commit()
    return int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])


def _two_sections(conn, group_id) -> "tuple[str, str]":
    """The two renderers that described g10941 both ways, built from the
    same connection: `## Lines in flight` and `## Recent decisions`."""
    from Tooling.agent import phase2_context
    from Tooling.pipeline.strategist import audit
    lines = audit.render_lines_section(
        audit.in_flight_lines(conn, "p", group_id))
    replay = phase2_context._section_failure_replay(conn, "p")
    return "\n".join(lines), "\n".join(replay)


def test_a_goal_no_worker_is_on_is_never_rendered_as_running(conn):
    """12:25 — Context said the Inject was PARKED with no worker and no
    wake coming, and 125 lines later listed the same goal as a
    dispatched line still running. `## Lines in flight` gated on the
    goal's STATUS (`attempting`), the replay on whether work is moving.
    An `attempting` goal with nothing under it and no worker satisfies
    the first and fails the second."""
    top = groups_store.ensure_top_group(conn, "p")
    root = _p_goal(conn, "root", status="attempting")
    _p_inject(conn, top, root)
    conn.commit()
    lines, replay = _two_sections(conn, top)
    assert "PARKED" in replay, replay
    assert "root" in lines, lines
    assert "NO worker on this line" in lines, lines
    assert "a worker is on this line" not in lines


def test_a_goal_with_a_running_pipeline_is_never_called_parked(conn):
    top = groups_store.ensure_top_group(conn, "p")
    root = _p_goal(conn, "root", status="attempting")
    _p_inject(conn, top, root)
    db.record_pipeline_start(conn, pipeline_id="live1", kind="Backward",
                             target_id=str(root), target_kind="Goal")
    conn.commit()
    assert db.has_running_pipeline_for_goal(conn, root)
    lines, replay = _two_sections(conn, top)
    assert "PARKED" not in replay, replay
    assert "a worker is on this line" in lines, lines
    assert "NO worker on this line" not in lines


def test_a_line_whose_work_moved_down_the_subtree_is_still_running(conn):
    """The worker arm is the SUBTREE's, not the root's: a Backward on a
    descendant is the line running. Narrowing it to the root node would
    drop live lines out of the audit's own roster."""
    from Tooling.pipeline.strategist import audit
    top = groups_store.ensure_top_group(conn, "p")
    root = _p_goal(conn, "root", status="attempting")
    sid = db.insert_strategy(conn, goal_id=root,
                             lean_path="Problems/p/proofs/L_root.lean",
                             created_by="pipe")
    kid = _p_goal(conn, "kid", status="open", depth=1)
    db.link_subgoal(conn, strategy_id=sid, subgoal_id=kid, position=0)
    _p_inject(conn, top, root)
    conn.commit()
    assert not db.has_running_pipeline_for_goal(conn, root)
    lines, replay = _two_sections(conn, top)
    assert "PARKED" not in replay, replay
    assert "a worker is on this line" in lines, lines


def test_the_audit_still_rules_on_a_line_no_worker_holds(conn):
    """A stalled line is exactly what criteria 3 and 4 exist for, so
    the worker state annotates the roster — it does not filter it."""
    from Tooling.pipeline.strategist import audit
    top = groups_store.ensure_top_group(conn, "p")
    root = _p_goal(conn, "root", status="attempting")
    _p_inject(conn, top, root)
    conn.commit()
    ids = [ln["goal_id"] for ln in audit.in_flight_lines(conn, "p", top)]
    assert ids == [root]


