"""`db.reconcile_settled_inject_outcomes` — resolve NULL-outcome Inject
batch decisions whose produced work has SETTLED, so a permanently-NULL
outcome can't keep suppressing the T4 stall trigger / blocking
`inject_batch_done`.

Root cause it addresses (2026-06-13, P13 stokes): a soft-shelved subgoal
keeps its parent strategy 'proposed' (awaiting a Reopen). When that
strategy was produced by an Inject(Backward), the decision's
`produced_goal_id`=target only terminates at problem end, so the NULL
outcome suppresses T4 (`problems_stalled`'s in-flight clause) → no
Strategist ever fires to perform the Reopen → permanent wedge. Plus
Inject(Forward) decisions whose produced goal reached a terminal status
without the goal-side propagation ever firing.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from Tooling.state import db


@pytest.fixture
def conn(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> sqlite3.Connection:
    monkeypatch.chdir(tmp_path)
    c = db.connect()
    db.init_schema(c)
    c.execute(
        "INSERT INTO problems (name, manifest_path, created_at, bootstrap_done)"
        " VALUES ('p', 'Problems/p/Manifest.md', ?, 1)",
        (db.now(),),
    )
    c.commit()
    return c


def _goal(conn: sqlite3.Connection, *, slug: str, status: str = "open",
          origin: str = "backward", problem: str = "p") -> int:
    cur = conn.execute(
        "INSERT INTO goals (problem, slug, lean_path, statement,"
        " kind, origin, status, depth, attempts, entry_kind,"
        " integrity_verified, detached, created_at, updated_at)"
        " VALUES (?, ?, ?, 'T', 'theorem', ?, ?, 0, 0, 'Builder', 0, 0, ?, ?)",
        (problem, slug, f"Problems/{problem}/proofs/L_{slug}.lean",
         origin, status, db.now(), db.now()),
    )
    conn.commit()
    return int(cur.lastrowid)


def _strategy(conn: sqlite3.Connection, *, goal_id: int,
              status: str = "proposed") -> int:
    cur = conn.execute(
        "INSERT INTO strategies (goal_id, lean_path, scratch_path,"
        " status, proposal_md, created_by, created_at)"
        " VALUES (?, '', '', ?, '', 'test', ?)",
        (goal_id, status, db.now()),
    )
    conn.commit()
    return int(cur.lastrowid)


def _link(conn: sqlite3.Connection, strategy_id: int,
          subgoal_ids: list[int]) -> None:
    for pos, sg in enumerate(subgoal_ids):
        conn.execute(
            "INSERT INTO strategy_subgoals (strategy_id, subgoal_id, position)"
            " VALUES (?, ?, ?)",
            (strategy_id, sg, pos),
        )
    conn.commit()


def _inject(conn: sqlite3.Connection, *, batch_id: str | None,
            produced_goal_id: int | None = None,
            produced_strategy_id: int | None = None,
            outcome: str | None = None, problem: str = "p") -> int:
    ts = db.now()
    cur = conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, target_id, brief, reason, payload,"
        " batch_id, produced_goal_id, produced_strategy_id, outcome,"
        " created_at, updated_at)"
        " VALUES (?, 0, 'pending_review', 'Inject', NULL, 'b', NULL, '{}',"
        "         ?, ?, ?, ?, ?, ?)",
        (problem, batch_id, produced_goal_id, produced_strategy_id,
         outcome, ts, ts),
    )
    conn.commit()
    return int(cur.lastrowid)


def _outcome(conn: sqlite3.Connection, did: int) -> str | None:
    r = conn.execute(
        "SELECT outcome FROM strategist_decisions WHERE id = ?", (did,),
    ).fetchone()
    return r["outcome"]


def _status(conn: sqlite3.Connection, table: str, rid: int) -> str:
    r = conn.execute(
        f"SELECT status FROM {table} WHERE id = ?", (rid,),
    ).fetchone()
    return str(r["status"])


def _n_strategist_queued(conn: sqlite3.Connection) -> int:
    return int(conn.execute(
        "SELECT COUNT(*) AS n FROM queue WHERE kind = 'Strategist'",
    ).fetchone()["n"])


# ---------------------------------------------------------------------
# Forward inject — resolved off the produced goal's terminal status
# ---------------------------------------------------------------------

def test_forward_shelved_goal_resolved_failed(conn: sqlite3.Connection) -> None:
    _goal(conn, slug="main", origin="root", status="attempting")
    g = _goal(conn, slug="lemma", status="shelved")
    did = _inject(conn, batch_id="b1", produced_goal_id=g)
    assert db.reconcile_settled_inject_outcomes(conn) == 1
    assert _outcome(conn, did) == "failed:shelved"
    # single-row batch now complete → one Strategist enqueued
    assert _n_strategist_queued(conn) == 1


def test_forward_proved_goal_resolved_success(conn: sqlite3.Connection) -> None:
    _goal(conn, slug="main", origin="root", status="attempting")
    g = _goal(conn, slug="lemma", status="proved")
    did = _inject(conn, batch_id="b1", produced_goal_id=g)
    assert db.reconcile_settled_inject_outcomes(conn) == 1
    assert _outcome(conn, did) == "success"


def test_forward_nonterminal_goal_left_alone(conn: sqlite3.Connection) -> None:
    """An open produced goal is genuinely in flight → not resolved."""
    _goal(conn, slug="main", origin="root", status="attempting")
    g = _goal(conn, slug="lemma", status="open")
    did = _inject(conn, batch_id="b1", produced_goal_id=g)
    assert db.reconcile_settled_inject_outcomes(conn) == 0
    assert _outcome(conn, did) is None


# ---------------------------------------------------------------------
# Backward inject — resolved off the produced strategy
# ---------------------------------------------------------------------

def test_backward_dead_strategy_resolved(conn: sqlite3.Connection) -> None:
    _goal(conn, slug="main", origin="root", status="attempting")
    tgt = _goal(conn, slug="target", status="attempting")
    s = _strategy(conn, goal_id=tgt, status="dead")
    did = _inject(conn, batch_id="b1", produced_goal_id=tgt,
                  produced_strategy_id=s)
    assert db.reconcile_settled_inject_outcomes(conn) == 1
    assert _outcome(conn, did) == "failed:dead"


def test_backward_deadlocked_proposed_strategy_resolved_stalled(
    conn: sqlite3.Connection,
) -> None:
    """The P13 wedge: strategy 'proposed' but every subgoal terminal (one
    soft-shelved) → resolve the DECISION 'failed:stalled', leaving the
    strategy/goal lifecycle untouched (the fired Strategist makes the
    real Reopen call)."""
    _goal(conn, slug="main", origin="root", status="attempting")
    tgt = _goal(conn, slug="target", status="attempting")
    s = _strategy(conn, goal_id=tgt, status="proposed")
    sg_ok = _goal(conn, slug="sg_ok", status="proved")
    sg_shelved = _goal(conn, slug="sg_shelved", status="shelved")
    _link(conn, s, [sg_ok, sg_shelved])
    did = _inject(conn, batch_id="b1", produced_goal_id=tgt,
                  produced_strategy_id=s)
    assert db.reconcile_settled_inject_outcomes(conn) == 1
    assert _outcome(conn, did) == "failed:stalled"
    # lifecycle untouched — Strategist owns the Reopen/ConfirmShelve call
    assert _status(conn, "strategies", s) == "proposed"
    assert _status(conn, "goals", sg_shelved) == "shelved"
    assert _status(conn, "goals", tgt) == "attempting"
    # batch complete → Strategist woken to act on the wedge
    assert _n_strategist_queued(conn) == 1


def test_backward_all_proved_proposed_strategy_resolved_success(
    conn: sqlite3.Connection,
) -> None:
    """Edge: a 'proposed' strategy whose subgoals all proved (a missed
    verify) resolves the decision 'success', not failed."""
    _goal(conn, slug="main", origin="root", status="attempting")
    tgt = _goal(conn, slug="target", status="attempting")
    s = _strategy(conn, goal_id=tgt, status="proposed")
    sg1 = _goal(conn, slug="sg1", status="proved")
    sg2 = _goal(conn, slug="sg2", status="proved")
    _link(conn, s, [sg1, sg2])
    did = _inject(conn, batch_id="b1", produced_goal_id=tgt,
                  produced_strategy_id=s)
    assert db.reconcile_settled_inject_outcomes(conn) == 1
    assert _outcome(conn, did) == "success"


def test_backward_proposed_with_alive_subgoal_left_alone(
    conn: sqlite3.Connection,
) -> None:
    """A 'proposed' strategy with an alive (open) subgoal is genuinely in
    flight → not resolved (in-flight safe)."""
    _goal(conn, slug="main", origin="root", status="attempting")
    tgt = _goal(conn, slug="target", status="attempting")
    s = _strategy(conn, goal_id=tgt, status="proposed")
    sg1 = _goal(conn, slug="sg1", status="proved")
    sg2 = _goal(conn, slug="sg2", status="open")
    _link(conn, s, [sg1, sg2])
    did = _inject(conn, batch_id="b1", produced_goal_id=tgt,
                  produced_strategy_id=s)
    assert db.reconcile_settled_inject_outcomes(conn) == 0
    assert _outcome(conn, did) is None


def test_backward_proposed_no_subgoals_left_alone(
    conn: sqlite3.Connection,
) -> None:
    """A 'proposed' strategy with NO subgoals yet (mid-spawn) is not
    treated as deadlocked."""
    _goal(conn, slug="main", origin="root", status="attempting")
    tgt = _goal(conn, slug="target", status="attempting")
    s = _strategy(conn, goal_id=tgt, status="proposed")
    did = _inject(conn, batch_id="b1", produced_goal_id=tgt,
                  produced_strategy_id=s)
    assert db.reconcile_settled_inject_outcomes(conn) == 0
    assert _outcome(conn, did) is None


# ---------------------------------------------------------------------
# Guards: batch_id required, scope filter, idempotence
# ---------------------------------------------------------------------

def test_null_batch_id_not_touched(conn: sqlite3.Connection) -> None:
    """A solo inject (batch_id NULL) does not suppress T4 in the first
    place (`problems_stalled` requires batch_id NOT NULL), so reconcile
    leaves it alone."""
    _goal(conn, slug="main", origin="root", status="attempting")
    g = _goal(conn, slug="lemma", status="shelved")
    did = _inject(conn, batch_id=None, produced_goal_id=g)
    assert db.reconcile_settled_inject_outcomes(conn) == 0
    assert _outcome(conn, did) is None


def test_scope_filter(conn: sqlite3.Connection) -> None:
    _goal(conn, slug="main", origin="root", status="attempting")
    g = _goal(conn, slug="lemma", status="shelved")
    did = _inject(conn, batch_id="b1", produced_goal_id=g)
    assert db.reconcile_settled_inject_outcomes(conn, scope="other%") == 0
    assert _outcome(conn, did) is None
    assert db.reconcile_settled_inject_outcomes(conn, scope="p") == 1
    assert _outcome(conn, did) == "failed:shelved"


def test_idempotent_second_pass_is_noop(conn: sqlite3.Connection) -> None:
    _goal(conn, slug="main", origin="root", status="attempting")
    g = _goal(conn, slug="lemma", status="shelved")
    _inject(conn, batch_id="b1", produced_goal_id=g)
    assert db.reconcile_settled_inject_outcomes(conn) == 1
    assert db.reconcile_settled_inject_outcomes(conn) == 0
