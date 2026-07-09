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

from Tooling.core import dispatcher as disp
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

def test_forward_shelved_goal_not_resolved(conn: sqlite3.Connection) -> None:
    """A shelved (parked, reopenable) produced goal does NOT settle its
    inject — outcome stays NULL and NO inject_batch_done fires. Shelved is a
    soft terminal: settling it re-fired the Strategist on every park (the P13
    4284 futile spin, 2026-06-15). T4's active-check (`has_active_inflight_
    inject`), not a settled outcome, governs re-engagement of a parked
    brick."""
    _goal(conn, slug="main", origin="root", status="attempting")
    g = _goal(conn, slug="lemma", status="shelved")
    did = _inject(conn, batch_id="b1", produced_goal_id=g)
    assert db.reconcile_settled_inject_outcomes(conn) == 0
    assert _outcome(conn, did) is None
    assert _n_strategist_queued(conn) == 0


def test_forward_proved_goal_resolved_success(conn: sqlite3.Connection) -> None:
    _goal(conn, slug="main", origin="root", status="attempting")
    g = _goal(conn, slug="lemma", status="proved")
    did = _inject(conn, batch_id="b1", produced_goal_id=g)
    assert db.reconcile_settled_inject_outcomes(conn) == 1
    assert _outcome(conn, did) == "success"
    # single-row batch now complete → one Strategist enqueued
    assert _n_strategist_queued(conn) == 1


def test_forward_dead_goal_resolved_failed(conn: sqlite3.Connection) -> None:
    """A hard-terminal (dead) produced goal still settles its inject — only
    `shelved` was dropped from the settling set."""
    _goal(conn, slug="main", origin="root", status="attempting")
    g = _goal(conn, slug="lemma", status="dead")
    did = _inject(conn, batch_id="b1", produced_goal_id=g)
    assert db.reconcile_settled_inject_outcomes(conn) == 1
    assert _outcome(conn, did) == "failed:dead"


def test_propagate_from_goal_status_mapping(conn: sqlite3.Connection) -> None:
    """Unit: propagate_inject_outcome_from_goal — proved→success,
    disproved/dead→failed:<status>, shelved/open/attempting→None (not a
    settling status; shelved is reopenable)."""
    _goal(conn, slug="main", origin="root", status="attempting")
    cases = {
        "proved": "success",
        "disproved": "failed:disproved",
        "dead": "failed:dead",
        "shelved": None,
        "open": None,
        "attempting": None,
    }
    for status, expected in cases.items():
        g = _goal(conn, slug=f"g_{status}", status=status)
        did = _inject(conn, batch_id=f"b_{status}", produced_goal_id=g)
        db.propagate_inject_outcome_from_goal(conn, g)
        assert _outcome(conn, did) == expected, status


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
    soft-shelved). Phase 11: PARK the strategy as 'stalled', which fills
    the producing inject's outcome 'failed:stalled' WITHOUT waking the
    Strategist. The parked-collapse wake is T4's call (is_problem_stalled),
    not an unconditional inject_batch_done — an immediate wake here re-plans
    work a prior run already pivoted on (the duplicate-wake 'stalled' was
    added to kill). The strategy stays reopenable (a subgoal Reopen flips
    it back to 'proposed')."""
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
    # strategy PARKED as 'stalled' (consistent + reopenable), not left
    # 'proposed' (the overloaded state that wedged the outcome at NULL).
    assert _status(conn, "strategies", s) == "stalled"
    assert _status(conn, "goals", sg_shelved) == "shelved"
    assert _status(conn, "goals", tgt) == "attempting"
    # NO Strategist woken: a collapse no longer fires inject_batch_done —
    # T4 decides whether a wake is owed (it isn't, if sibling injects left
    # alive alternatives). This is the duplicate-wake fix.
    assert _n_strategist_queued(conn) == 0


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
    place (`reconcile`/active-check require batch_id NOT NULL), so reconcile
    leaves it alone even when its produced goal is hard-terminal."""
    _goal(conn, slug="main", origin="root", status="attempting")
    g = _goal(conn, slug="lemma", status="proved")
    did = _inject(conn, batch_id=None, produced_goal_id=g)
    assert db.reconcile_settled_inject_outcomes(conn) == 0
    assert _outcome(conn, did) is None


def test_scope_filter(conn: sqlite3.Connection) -> None:
    _goal(conn, slug="main", origin="root", status="attempting")
    g = _goal(conn, slug="lemma", status="proved")
    did = _inject(conn, batch_id="b1", produced_goal_id=g)
    assert db.reconcile_settled_inject_outcomes(conn, scope="other%") == 0
    assert _outcome(conn, did) is None
    assert db.reconcile_settled_inject_outcomes(conn, scope="p") == 1
    assert _outcome(conn, did) == "success"


def test_idempotent_second_pass_is_noop(conn: sqlite3.Connection) -> None:
    _goal(conn, slug="main", origin="root", status="attempting")
    g = _goal(conn, slug="lemma", status="proved")
    _inject(conn, batch_id="b1", produced_goal_id=g)
    assert db.reconcile_settled_inject_outcomes(conn) == 1
    assert db.reconcile_settled_inject_outcomes(conn) == 0


# ---------------------------------------------------------------------
# Phase 11 — 'stalled' strategy status: the PRIMARY (shelve-time) path
# that replaces the reconcile band-aid. `_propagate_shelve` parks a
# parent strategy whose sub-goals all settled, filling the producing
# inject's outcome WITHOUT an unconditional Strategist wake.
# ---------------------------------------------------------------------

def test_shelve_parks_parent_strategy_stalled(conn: sqlite3.Connection) -> None:
    """Soft-shelving the last alive sub-goal of a 'proposed' parent
    strategy parks it 'stalled' at shelve-time: the producing inject's
    outcome fills 'failed:stalled'. This is the primary path; the
    reconcile is only a backstop.

    2026-07-09 (putnam_2025_b6 mutual-deadlock fix B): if that parked
    strategy was the goal's LAST live route, the goal escalates to
    pending_strategist_review and a T2 Strategist IS enqueued — the old
    "the wake is T4's call" stance left an `attempting` goal nobody
    would ever touch (and cond-4 could suppress the very T4 it
    deferred to)."""
    _goal(conn, slug="main", origin="root", status="attempting")
    g = _goal(conn, slug="target", status="attempting")
    s = _strategy(conn, goal_id=g, status="proposed")
    sg_ok = _goal(conn, slug="sg_ok", status="proved")
    sg_x = _goal(conn, slug="sg_x", status="open")
    _link(conn, s, [sg_ok, sg_x])
    did = _inject(conn, batch_id="b1", produced_goal_id=g,
                  produced_strategy_id=s)

    # Shelve the last alive sub-goal via the production sequence.
    db.update_goal_status(conn, sg_x, "shelved")
    disp._propagate_shelve(conn, sg_x)

    assert _status(conn, "strategies", s) == "stalled"
    assert _outcome(conn, did) == "failed:stalled"
    # Fix B: last-route park escalates the goal + enqueues the T2 review.
    assert db.get_goal(conn, g)["status"] == "pending_strategist_review"
    assert _n_strategist_queued(conn) == 1


def test_shelve_with_alive_sibling_keeps_parent_proposed(
    conn: sqlite3.Connection,
) -> None:
    """A parent strategy that still has an alive sibling is genuinely in
    flight → stays 'proposed', inject outcome stays NULL."""
    _goal(conn, slug="main", origin="root", status="attempting")
    g = _goal(conn, slug="target", status="attempting")
    s = _strategy(conn, goal_id=g, status="proposed")
    sg_alive = _goal(conn, slug="sg_alive", status="open")
    sg_x = _goal(conn, slug="sg_x", status="open")
    _link(conn, s, [sg_alive, sg_x])
    did = _inject(conn, batch_id="b1", produced_goal_id=g,
                  produced_strategy_id=s)

    db.update_goal_status(conn, sg_x, "shelved")
    disp._propagate_shelve(conn, sg_x)

    assert _status(conn, "strategies", s) == "proposed"
    assert _outcome(conn, did) is None


def test_shelve_with_dead_sibling_not_parked(conn: sqlite3.Connection) -> None:
    """A hard-terminal (dead) sibling means the decomposition is wrong, not
    merely parked — left for `_kill_upward_chain` to mark 'dead'. The soft
    stall transition skips it (stays 'proposed')."""
    _goal(conn, slug="main", origin="root", status="attempting")
    g = _goal(conn, slug="target", status="attempting")
    s = _strategy(conn, goal_id=g, status="proposed")
    sg_dead = _goal(conn, slug="sg_dead", status="dead")
    sg_x = _goal(conn, slug="sg_x", status="open")
    _link(conn, s, [sg_dead, sg_x])

    db.update_goal_status(conn, sg_x, "shelved")
    disp._propagate_shelve(conn, sg_x)

    assert _status(conn, "strategies", s) == "proposed"


def test_stalled_lifts_t4_suppression(conn: sqlite3.Connection) -> None:
    """The fix end-to-end: while a root-decompose inject's strategy is in
    flight (alive sub-goal) the problem is NOT stalled; once its last
    sub-goal soft-shelves, the parent parks 'stalled' (outcome filled), so
    `problems_stalled` — no longer suppressed by the NULL outcome and seeing
    no alive-reachable open goal — flags the collapse for T4."""
    r = _goal(conn, slug="main", origin="root", status="attempting")
    sr = _strategy(conn, goal_id=r, status="proposed")
    g = _goal(conn, slug="target", status="attempting")
    _link(conn, sr, [g])
    s = _strategy(conn, goal_id=g, status="proposed")
    sg_x = _goal(conn, slug="sg_x", status="open")
    _link(conn, s, [sg_x])
    did = _inject(conn, batch_id="b1", produced_goal_id=g,
                  produced_strategy_id=s)

    # In flight: sg_x open and reachable from root → not stalled.
    assert db.problems_stalled(conn, scope="p") == []

    db.update_goal_status(conn, sg_x, "shelved")
    disp._propagate_shelve(conn, sg_x)

    # Collapsed: parent parked 'stalled', outcome filled (suppression
    # lifted), no alive-reachable open goal → flagged for T4.
    assert _status(conn, "strategies", s) == "stalled"
    assert _outcome(conn, did) == "failed:stalled"
    assert db.problems_stalled(conn, scope="p") == ["p"]
