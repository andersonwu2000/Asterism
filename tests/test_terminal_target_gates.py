"""A terminal target accepts no new work (owner ruling 2026-08-19).

The fact used to live in ONE home — the dispatch stale-drop — and only
for Strategist rows. Fold day supplied the live counterexample: g464 and
g485 were cascade-closed at 11:02Z while their own Strategist wakes were
mid-dialogue; both debated on to adversary round 11 (pure burn), and the
commit path would have accepted the survivor's batch against a closed
group. Four doors now hold it:

  1. dispatch (`_row_is_stale`) — Strategist rows on retired groups AND
     Formalizer/Builder rows on settled goals drop before the spawn is
     paid;
  2. the wake's round boundary + pre-commit (`_group_retired_status`) —
     an in-flight dialogue self-aborts instead of debating on;
  3. `commit_decisions` — the any-caller backstop, raising;
  4. `open_group` — a retired parent delegates nothing (a Delegate that
     somehow reached commit cannot resurrect a folded tree).

What must NOT regress: proof-beats-shelve (a kernel proof landing on a
mid-flight-shelved goal still upgrades it — killing or dropping that
work forfeits true theorems), and the dual-anchor race (two groups on
one goal is legal; the loser's landing is idempotent)."""
from __future__ import annotations

import sqlite3

import pytest

from Tooling.state import db
from Tooling.state import groups as _groups


def _mk_problem(conn: sqlite3.Connection, name: str) -> int:
    conn.execute(
        "INSERT INTO problems (name, created_at, bootstrap_done)"
        " VALUES (?, ?, 1)", (name, db.now()))
    return _groups.ensure_top_group(conn, name, charter="Prove it.")


# ── door 1: dispatch ─────────────────────────────────────────────────


def test_goal_row_is_stale_when_goal_settled(
        conn: sqlite3.Connection) -> None:
    from Tooling.core.dispatcher import _row_is_stale
    _mk_problem(conn, "p")
    gid = db.insert_goal(
        conn, problem="p", slug="g1", lean_path="Problems/p/Root.lean",
        statement="T", origin="root")
    # Live statuses dispatch; `attempting` covers the rescue shape
    # (Delegate promotes its anchor before the row pops).
    for live in ("open", "attempting"):
        conn.execute("UPDATE goals SET status = ? WHERE id = ?",
                     (live, gid))
        for kind in ("Formalizer", "Builder"):
            assert _row_is_stale(conn, str(gid), kind, "Goal") is False, (
                live, kind)
    # A settled goal's row drops before the spawn is paid.
    for settled in ("proved", "shelved", "disproved",
                    "pending_strategist_review"):
        conn.execute("UPDATE goals SET status = ? WHERE id = ?",
                     (settled, gid))
        assert _row_is_stale(conn, str(gid), "Formalizer", "Goal") \
            is True, settled
    # Goal ids are never reused — a row naming a missing goal is garbage.
    assert _row_is_stale(conn, "999999", "Formalizer", "Goal") is True
    # Non-goal-workers on Goal targets are not this arm's business.
    assert _row_is_stale(conn, str(gid), "Strategist", "Goal") is False


# ── door 2: the wake's own status check ──────────────────────────────


def test_group_retired_status_sees_every_terminal(
        conn: sqlite3.Connection) -> None:
    from Tooling.pipeline.strategist import _group_retired_status
    top = _mk_problem(conn, "p")
    sub = _groups.open_group(conn, problem="p", parent_group_id=top,
                             charter="Case A.")
    assert _group_retired_status(conn, "p", sub) is None
    for terminal in _groups.TERMINAL_STATUSES:
        conn.execute("UPDATE groups SET status = ? WHERE id = ?",
                     (terminal, sub))
        assert _group_retired_status(conn, "p", sub) == terminal


def test_group_retired_status_resolves_none_to_top(
        conn: sqlite3.Connection) -> None:
    """`group_id=None` means the top group (hand-driven callers) — a
    post-Ingest ghost wake on a delivered top group is the same disease
    (2026-08-13/14: groups 383/381, four post-delivery batches)."""
    from Tooling.pipeline.strategist import _group_retired_status
    top = _mk_problem(conn, "p")
    assert _group_retired_status(conn, "p", None) is None
    conn.execute("UPDATE groups SET status = 'delivered' WHERE id = ?",
                 (top,))
    assert _group_retired_status(conn, "p", None) == "delivered"


# ── door 3: commit backstop ──────────────────────────────────────────


def test_commit_decisions_refuses_a_retired_group(
        conn: sqlite3.Connection, tmp_path) -> None:
    from Tooling.pipeline.strategist import Decision, commit_decisions
    top = _mk_problem(conn, "p")
    sub = _groups.open_group(conn, problem="p", parent_group_id=top,
                             charter="Case A.")
    conn.execute("UPDATE groups SET status = 'closed' WHERE id = ?",
                 (sub,))
    conn.commit()
    with pytest.raises(ValueError, match="retired charter"):
        commit_decisions(
            [Decision(kind="Noop", reason="nothing to do")],
            conn, problem="p", tick=0, trigger_kind="routine",
            workspace=tmp_path, group_id=sub)


# ── door 4: open_group ───────────────────────────────────────────────


def test_open_group_refuses_a_terminal_parent(
        conn: sqlite3.Connection) -> None:
    top = _mk_problem(conn, "p")
    sub = _groups.open_group(conn, problem="p", parent_group_id=top,
                             charter="Case A.")
    for terminal in _groups.TERMINAL_STATUSES:
        conn.execute("UPDATE groups SET status = ? WHERE id = ?",
                     (terminal, sub))
        with pytest.raises(ValueError, match="delegates nothing"):
            _groups.open_group(conn, problem="p", parent_group_id=sub,
                               charter="Sub-case A.1.")
    # A live parent still opens children — the gate is on terminals only.
    conn.execute("UPDATE groups SET status = 'active' WHERE id = ?",
                 (sub,))
    assert _groups.open_group(conn, problem="p", parent_group_id=sub,
                              charter="Sub-case A.1.") > 0


# ── the registry entry ───────────────────────────────────────────────


def test_group_retired_is_registered_and_not_infra() -> None:
    """`group_retired` must not be infra: infra Strategist failures
    re-enqueue the wake, and the re-enqueued row would only meet the
    dispatch stale-drop — a retry loop with extra steps."""
    from Tooling.state import failures
    assert "group_retired" in failures.REGISTRY
    assert failures.is_infra("group_retired") is False


# ── what must NOT regress ────────────────────────────────────────────


def test_proof_still_beats_shelve(conn: sqlite3.Connection) -> None:
    """A goal shelved mid-flight is a soft park, not a verdict: the
    in-flight prover's kernel proof still upgrades it. This is why the
    kill/drop criterion is 'own target settled', never 'sibling
    shelved' — dropping here would forfeit true theorems."""
    from Tooling.state import transitions
    assert ("shelved", "proved") in transitions.GOAL_EDGES
    _mk_problem(conn, "p")
    gid = db.insert_goal(
        conn, problem="p", slug="g1", lean_path="Problems/p/Root.lean",
        statement="T", origin="root")
    conn.execute("UPDATE goals SET status = 'shelved' WHERE id = ?",
                 (gid,))
    transitions.apply_goal_transition(
        conn, gid, "proved", event="test_revival",
        receipt=transitions.ProvedReceipt("axiom_gate", "test"))
    row = conn.execute("SELECT status FROM goals WHERE id = ?",
                       (gid,)).fetchone()
    assert str(row["status"]) == "proved"
