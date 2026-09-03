"""`disproved` is a KERNEL verdict again (owner ruling 2026-09-04),
after eighteen days as a claimed one (owner ruling 2026-08-18).

The 08-18 incident: an intake worker's prose counterexample flipped
`fin5_block_row_40_true` (g8014) to hard-terminal `disproved` at
01:54; `#eval` of the landed checker later proved the claim TRUE. All
8 of union_closed's disproved goals were prose-flipped `sorry` files,
dedupe's `same_as_disproved` blocked every re-proposal, and two
Programme revisions were built on the false negative — an unfixable
wrong verdict defended by the framework itself.

The sequel LANDED (`_disprove.run_disproof_gate` is now the only road
to `agent_infeasible`), so 2026-09-04 closes the demotion back up: a
`disproved` mark is a KERNEL-certified refutation, and a strategist
Inject may not overturn one by fiat. The way out of a refutation is a
different statement, not a louder argument about the same one.

What remains of the 08-18 shape is deliberately NARROW:
  * the ("disproved","open") FSM edge stays, for OPERATOR repair only
    — a person who finds the gate itself was wrong;
  * everything read-side keeps treating disproved as settled: it stays
    in GOAL_HARD_TERMINALS, citing one is an error, dedupe blocks twin
    mints, and `verify_decision` refuses the Inject with the way out.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from Tooling.state import db as _db
from Tooling.state import transitions

_PROMPTS = Path(__file__).resolve().parents[1] / "Tooling" / "prompts"


def _seed(conn: sqlite3.Connection, slug: str, status: str) -> int:
    conn.execute(
        "INSERT INTO problems (name, created_at,"
        " bootstrap_done)"
        " SELECT 'P', ?, 1 WHERE NOT EXISTS"
        " (SELECT 1 FROM problems WHERE name = 'P')", (_db.now(),))
    gid = _db.insert_goal(
        conn, problem="P", slug=slug, lean_path=f"P/L_{slug}.lean",
        statement="S", origin="backward")
    conn.execute("UPDATE goals SET status = ? WHERE id = ?", (status, gid))
    conn.commit()
    return gid


def test_a_disproved_goal_is_revivable_by_an_operator(
        conn: sqlite3.Connection) -> None:
    """The FSM edge survives for the repair case — a person who finds
    the disproof gate itself was wrong. Only the agent-facing route
    (Inject) is closed; see below."""
    gid = _seed(conn, "claimed_false", "disproved")
    transitions.apply_goal_transition(
        conn, gid, "open", event="strategist_reopen")
    assert _db.get_goal(conn, gid)["status"] == "open"
    ev = conn.execute(
        "SELECT event FROM goal_events WHERE goal_id = ?"
        " ORDER BY id DESC LIMIT 1", (gid,)).fetchone()
    assert ev is not None and ev["event"] == "strategist_reopen"


def test_an_inject_on_a_disproved_goal_is_refused_with_the_way_out(
        conn: sqlite3.Connection) -> None:
    """A kernel-certified refutation is not revived by fiat. The refusal
    is a teaching moment, so it must name the reachable move: mint a new
    statement, do not re-argue the refuted one."""
    from Tooling.pipeline.strategist import Decision, verify_decision
    gid = _seed(conn, "claimed_false2", "disproved")
    err = verify_decision(
        Decision(kind="Inject", target_id=gid,
                 brief="Theorem. the claim holds after all.\nProof. the claimed "
                       "counterexample fails: row 40 checks out by the "
                       "landed defs."),
        conn, problem="P")
    assert "disproved" in err
    assert "kernel" in err
    # The way out has to be an action the strategist can actually take.
    assert "new" in err.lower() and "statement" in err.lower()


def test_an_inject_on_a_proved_goal_is_refused(
        conn: sqlite3.Connection) -> None:
    g2 = _seed(conn, "really_done", "proved")
    from Tooling.pipeline.strategist import Decision, verify_decision
    err = verify_decision(
        Decision(kind="Inject", target_id=g2,
                 brief="Theorem. T.\nProof. again."),
        conn, problem="P")
    assert "'proved'" in err and "redispatch" in err


def test_the_read_side_still_treats_disproved_as_settled() -> None:
    """Pulling disproved out of the read-side sets would let citations
    pass, leave inject outcomes pending forever, and downgrade
    ConfirmShelve into a category eraser. The surviving FSM edge is an
    operator affordance, not a softening of the mark."""
    assert "disproved" in transitions.GOAL_HARD_TERMINALS
    assert "disproved" in transitions.GOAL_FAILED_TERMINALS
    assert ("disproved", "open") in transitions.GOAL_EDGES


