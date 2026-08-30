"""`disproved` is parked on a CLAIMED counterexample — not settled by
the kernel (owner ruling 2026-08-18).

The incident: an intake worker's prose counterexample flipped
`fin5_block_row_40_true` (g8014) to hard-terminal `disproved` at
01:54; `#eval` of the landed checker later proved the claim TRUE. All
8 of union_closed's disproved goals were prose-flipped `sorry` files,
dedupe's `same_as_disproved` blocked every re-proposal, and two
Programme revisions were built on the false negative — an unfixable
wrong verdict defended by the framework itself.

The demotion is deliberately NARROW:
  * a ("disproved","open") FSM edge exists — a strategist Inject (or
    an operator repair) revives one;
  * everything read-side keeps treating disproved as settled-unless-
    revived: it stays in GOAL_HARD_TERMINALS, citing one is still an
    error, dedupe still blocks twin mints (its message now teaches
    revival instead).
The kernel-witnessed disproof leg (a DisprovedReceipt mirroring
ProvedReceipt) is the deliberately unscheduled sequel.
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


def test_a_disproved_goal_is_revivable(conn: sqlite3.Connection) -> None:
    gid = _seed(conn, "claimed_false", "disproved")
    transitions.apply_goal_transition(
        conn, gid, "open", event="strategist_reopen")
    assert _db.get_goal(conn, gid)["status"] == "open"
    ev = conn.execute(
        "SELECT event FROM goal_events WHERE goal_id = ?"
        " ORDER BY id DESC LIMIT 1", (gid,)).fetchone()
    assert ev is not None and ev["event"] == "strategist_reopen"


def test_an_inject_on_a_disproved_goal_is_the_revival_route(
        conn: sqlite3.Connection) -> None:
    from Tooling.pipeline.strategist import Decision, verify_decision
    gid = _seed(conn, "claimed_false2", "disproved")
    assert verify_decision(
        Decision(kind="Inject", target_id=gid,
                 brief="Theorem. the claim holds after all.\nProof. the claimed "
                       "counterexample fails: row 40 checks out by the "
                       "landed defs."),
        conn, problem="P") == ""
    # proved / dead stay refused — those ARE kernel-settled (or
    # context-settled) and have no revival story here.
    for status, slug in (("proved", "really_done"), ("dead", "moot_ctx")):
        g2 = _seed(conn, slug, status)
        err = verify_decision(
            Decision(kind="Inject", target_id=g2, brief="Theorem. T.\nProof. again."),
            conn, problem="P")
        assert "proved/dead are hard terminals" in err, (status, err)


def test_the_read_side_still_treats_disproved_as_settled() -> None:
    """The demotion must stay narrow: pulling disproved out of the
    read-side sets would let citations pass, leave inject outcomes
    pending forever, and downgrade ConfirmShelve into a category
    eraser. The FSM edge is the whole change."""
    assert "disproved" in transitions.GOAL_HARD_TERMINALS
    assert "disproved" in transitions.GOAL_FAILED_TERMINALS
    assert ("disproved", "open") in transitions.GOAL_EDGES


