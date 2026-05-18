"""Phase 2 cascade rules — helper functions in dispatcher.py.

Covers:
  Rule 2 — `_cascade_shelve_descendants` (ConfirmShelve downward cascade)
  Rule 3 — `_has_terminal_disproved_ancestor` (Reopen safety walk)
           `_has_dead_strategy_in_chain` (auto-detach trigger detection)

Rule 1 (cascade_one decline-directive split) is covered in
`tests/test_infeasible_escape.py`.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from Tooling.core.dispatcher import (
    _cascade_shelve_descendants,
    _has_terminal_disproved_ancestor,
    _has_dead_strategy_in_chain,
    _enqueue_strategist_review,
    cascade_one,
)
from Tooling.state import db


@pytest.fixture
def conn(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> sqlite3.Connection:
    monkeypatch.chdir(tmp_path)
    c = db.connect()
    db.init_schema(c)
    c.execute(
        "INSERT INTO problems (name, manifest_path, created_at) "
        "VALUES ('p', 'Problems/p/Manifest.md', ?)",
        (db.now(),),
    )
    c.commit()
    return c


def _insert_goal(conn: sqlite3.Connection, *, slug: str,
                 origin: str = "backward", status: str = "open",
                 problem: str = "p") -> int:
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


def _insert_strategy(conn: sqlite3.Connection, *, goal_id: int,
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


# ---------------------------------------------------------------------
# Rule 2: _cascade_shelve_descendants
# ---------------------------------------------------------------------

def test_cascade_shelve_descendants_one_level(conn: sqlite3.Connection) -> None:
    """G with one strategy S, S claims sub_a (open) + sub_b (attempting).
    ConfirmShelve(G) cascades both descendants to 'shelved'."""
    g = _insert_goal(conn, slug="g", origin="root")
    s = _insert_strategy(conn, goal_id=g)
    sub_a = _insert_goal(conn, slug="sub_a", status="open")
    sub_b = _insert_goal(conn, slug="sub_b", status="attempting")
    _link(conn, s, [sub_a, sub_b])

    transitioned = _cascade_shelve_descendants(conn, g)
    assert transitioned == 2
    assert db.get_goal(conn, sub_a)["status"] == "shelved"
    assert db.get_goal(conn, sub_b)["status"] == "shelved"


def test_cascade_shelve_descendants_multi_level(conn: sqlite3.Connection) -> None:
    """G → S1 → sub_a → S2 → sub_b → S3 → sub_c. ConfirmShelve(G) walks
    the entire downward DAG, shelves all three descendants."""
    g = _insert_goal(conn, slug="g", origin="root")
    s1 = _insert_strategy(conn, goal_id=g)
    sub_a = _insert_goal(conn, slug="sub_a", status="open")
    _link(conn, s1, [sub_a])
    s2 = _insert_strategy(conn, goal_id=sub_a)
    sub_b = _insert_goal(conn, slug="sub_b", status="attempting")
    _link(conn, s2, [sub_b])
    s3 = _insert_strategy(conn, goal_id=sub_b)
    sub_c = _insert_goal(conn, slug="sub_c", status="open")
    _link(conn, s3, [sub_c])

    transitioned = _cascade_shelve_descendants(conn, g)
    assert transitioned == 3
    for sub in (sub_a, sub_b, sub_c):
        assert db.get_goal(conn, sub)["status"] == "shelved"


def test_cascade_shelve_descendants_preserves_terminals(
    conn: sqlite3.Connection,
) -> None:
    """proved / shelved / disproved descendants are preserved (not
    overwritten by the cascade)."""
    g = _insert_goal(conn, slug="g", origin="root")
    s = _insert_strategy(conn, goal_id=g)
    sub_proved = _insert_goal(conn, slug="sub_proved", status="proved")
    sub_disproved = _insert_goal(conn, slug="sub_disproved", status="disproved")
    sub_shelved_already = _insert_goal(conn, slug="sub_shelved_already",
                                       status="shelved")
    sub_open = _insert_goal(conn, slug="sub_open", status="open")
    _link(conn, s, [sub_proved, sub_disproved, sub_shelved_already, sub_open])

    transitioned = _cascade_shelve_descendants(conn, g)
    assert transitioned == 1  # only sub_open transitions
    assert db.get_goal(conn, sub_proved)["status"] == "proved"
    assert db.get_goal(conn, sub_disproved)["status"] == "disproved"
    assert db.get_goal(conn, sub_shelved_already)["status"] == "shelved"
    assert db.get_goal(conn, sub_open)["status"] == "shelved"


def test_cascade_shelve_descendants_transitions_pending_review(
    conn: sqlite3.Connection,
) -> None:
    """pending_strategist_review descendants transition to 'shelved'
    (Strategist confirmed the parent is dead; pending review on the
    descendant is now moot)."""
    g = _insert_goal(conn, slug="g", origin="root")
    s = _insert_strategy(conn, goal_id=g)
    sub = _insert_goal(conn, slug="sub", status="pending_strategist_review")
    _link(conn, s, [sub])

    transitioned = _cascade_shelve_descendants(conn, g)
    assert transitioned == 1
    assert db.get_goal(conn, sub)["status"] == "shelved"


def test_cascade_shelve_descendants_handles_dag(
    conn: sqlite3.Connection,
) -> None:
    """A shared sub-goal under two distinct strategies (DAG, not tree)
    is visited only once."""
    g = _insert_goal(conn, slug="g", origin="root")
    s1 = _insert_strategy(conn, goal_id=g)
    s2 = _insert_strategy(conn, goal_id=g)
    shared = _insert_goal(conn, slug="shared", status="open")
    _link(conn, s1, [shared])
    _link(conn, s2, [shared])

    transitioned = _cascade_shelve_descendants(conn, g)
    assert transitioned == 1  # not 2
    assert db.get_goal(conn, shared)["status"] == "shelved"


# ---------------------------------------------------------------------
# Rule 3: _has_terminal_disproved_ancestor
# ---------------------------------------------------------------------

def test_disproved_ancestor_detected(conn: sqlite3.Connection) -> None:
    """G → S → sub. Set G.status='disproved'. sub has a disproved
    ancestor."""
    g = _insert_goal(conn, slug="g", origin="root", status="disproved")
    s = _insert_strategy(conn, goal_id=g)
    sub = _insert_goal(conn, slug="sub", status="open")
    _link(conn, s, [sub])

    assert _has_terminal_disproved_ancestor(conn, sub) is True


def test_shelved_ancestor_not_a_terminal_block(
    conn: sqlite3.Connection,
) -> None:
    """`shelved` is soft terminal (reopenable). It does NOT block Reopen
    on a descendant — that's the point of the Phase 2 detach mechanism."""
    g = _insert_goal(conn, slug="g", origin="root", status="shelved")
    s = _insert_strategy(conn, goal_id=g)
    sub = _insert_goal(conn, slug="sub", status="shelved")
    _link(conn, s, [sub])

    assert _has_terminal_disproved_ancestor(conn, sub) is False


def test_no_ancestor_means_no_block(conn: sqlite3.Connection) -> None:
    """Root goal has no ancestor → no block."""
    g = _insert_goal(conn, slug="g", origin="root")
    assert _has_terminal_disproved_ancestor(conn, g) is False


def test_disproved_at_depth_2(conn: sqlite3.Connection) -> None:
    """G (open) → S1 → mid (disproved) → S2 → sub. Walk should find
    mid's status, return True."""
    g = _insert_goal(conn, slug="g", origin="root")
    s1 = _insert_strategy(conn, goal_id=g)
    mid = _insert_goal(conn, slug="mid", status="disproved")
    _link(conn, s1, [mid])
    s2 = _insert_strategy(conn, goal_id=mid)
    sub = _insert_goal(conn, slug="sub", status="open")
    _link(conn, s2, [sub])

    assert _has_terminal_disproved_ancestor(conn, sub) is True


# ---------------------------------------------------------------------
# Rule 3: _has_dead_strategy_in_chain (auto-detach trigger)
# ---------------------------------------------------------------------

def test_dead_strategy_in_chain_detected(conn: sqlite3.Connection) -> None:
    """G → S(dead) → sub. The dead strategy means sub is orphaned;
    a Reopen on sub should auto-detach it."""
    g = _insert_goal(conn, slug="g", origin="root")
    s = _insert_strategy(conn, goal_id=g, status="dead")
    sub = _insert_goal(conn, slug="sub", status="shelved")
    _link(conn, s, [sub])

    assert _has_dead_strategy_in_chain(conn, sub) is True


def test_superseded_strategy_in_chain_detected(
    conn: sqlite3.Connection,
) -> None:
    """Same as dead — a superseded strategy means downstream goals are
    orphaned from this branch."""
    g = _insert_goal(conn, slug="g", origin="root")
    s = _insert_strategy(conn, goal_id=g, status="superseded")
    sub = _insert_goal(conn, slug="sub", status="shelved")
    _link(conn, s, [sub])

    assert _has_dead_strategy_in_chain(conn, sub) is True


def test_alive_chain_no_detach(conn: sqlite3.Connection) -> None:
    """All strategies in the chain are proposed/succeeded → no detach
    needed. Reopen restores attempting without setting detached."""
    g = _insert_goal(conn, slug="g", origin="root")
    s = _insert_strategy(conn, goal_id=g, status="proposed")
    sub = _insert_goal(conn, slug="sub", status="open")
    _link(conn, s, [sub])

    assert _has_dead_strategy_in_chain(conn, sub) is False


def test_dead_at_depth_2(conn: sqlite3.Connection) -> None:
    """G → S1(dead) → mid → S2(proposed) → sub. The dead S1 means the
    whole chain is broken even if S2 is alive."""
    g = _insert_goal(conn, slug="g", origin="root")
    s1 = _insert_strategy(conn, goal_id=g, status="dead")
    mid = _insert_goal(conn, slug="mid", status="shelved")
    _link(conn, s1, [mid])
    s2 = _insert_strategy(conn, goal_id=mid, status="proposed")
    sub = _insert_goal(conn, slug="sub", status="open")
    _link(conn, s2, [sub])

    assert _has_dead_strategy_in_chain(conn, sub) is True


# ---------------------------------------------------------------------
# Rule 1 / dispatcher.cascade_one helper: _enqueue_strategist_review
# ---------------------------------------------------------------------

def test_enqueue_strategist_review_sets_status_and_queues(
    conn: sqlite3.Connection,
) -> None:
    """_enqueue_strategist_review marks goal pending and enqueues
    Strategist on this problem's root."""
    root = _insert_goal(conn, slug="main", origin="root")
    sub = _insert_goal(conn, slug="sub", status="attempting")

    _enqueue_strategist_review(conn, sub)

    assert db.get_goal(conn, sub)["status"] == "pending_strategist_review"
    q = conn.execute(
        "SELECT kind, target_id, priority FROM queue WHERE kind='Strategist'"
    ).fetchall()
    assert len(q) == 1
    assert int(q[0]["target_id"]) == root
    # Priority 20 per pipelines.md §2.1 (T2 > T0/T1=10); regression guard
    # against db.enqueue default=0 putting T2 below Backward / Builder.
    assert q[0]["priority"] == 20


def test_enqueue_strategist_review_dedups_in_flight(
    conn: sqlite3.Connection,
) -> None:
    """Two sub-goals shelving on the same problem produce only ONE
    Strategist queue entry. Per-problem in-flight dedup."""
    root = _insert_goal(conn, slug="main", origin="root")
    sub_a = _insert_goal(conn, slug="sub_a", status="attempting")
    sub_b = _insert_goal(conn, slug="sub_b", status="attempting")

    _enqueue_strategist_review(conn, sub_a)
    _enqueue_strategist_review(conn, sub_b)

    q = conn.execute(
        "SELECT COUNT(*) AS n FROM queue WHERE kind='Strategist'"
    ).fetchone()
    assert q["n"] == 1
    # Both sub-goals are pending
    assert db.get_goal(conn, sub_a)["status"] == "pending_strategist_review"
    assert db.get_goal(conn, sub_b)["status"] == "pending_strategist_review"


def test_forward_failure_re_enqueues_strategist_when_pending_review_exists(
    conn: sqlite3.Connection,
) -> None:
    """Forward outcome=failed must re-enqueue Strategist when there's a
    `pending_strategist_review` goal on the problem. Without this hook,
    after Strategist→Inject(Forward)→Forward fails, the queue drains
    to empty while the originating pending_review goal still waits for
    a verdict — daemon idle-exits before T1's 60-min wall-clock fires.
    SG run 2026-05-17 trace: cascade_one had no Forward branch, so a
    Forward failure was a state-side no-op."""
    root = _insert_goal(conn, slug="main", origin="root", status="attempting")
    pr = _insert_goal(conn, slug="kelly_contrapositive",
                      status="pending_strategist_review")

    cascade_one(
        conn, pipeline_id="pid-fwd", kind="Forward",
        target_id="p", target_kind="Problem",
        outcome="failed", failure_reason="forward_no_new_goal",
    )
    q = conn.execute(
        "SELECT kind, target_id FROM queue WHERE kind='Strategist'"
    ).fetchall()
    assert len(q) == 1
    assert int(q[0]["target_id"]) == root  # Strategist targets the root


def test_forward_success_does_not_re_enqueue_strategist(
    conn: sqlite3.Connection,
) -> None:
    """Forward success (lemma committed) does NOT re-enqueue Strategist
    — that's a separate decision. The pending_review goal would normally
    be unblocked by Backward retry seeing the new lemma via dedupe."""
    _insert_goal(conn, slug="main", origin="root", status="attempting")
    _insert_goal(conn, slug="pending_lemma",
                 status="pending_strategist_review")

    cascade_one(
        conn, pipeline_id="pid-fwd-ok", kind="Forward",
        target_id="p", target_kind="Problem",
        outcome="success",
    )
    q = conn.execute(
        "SELECT COUNT(*) AS n FROM queue WHERE kind='Strategist'"
    ).fetchone()
    assert q["n"] == 0


def test_forward_failure_no_op_when_no_pending_review(
    conn: sqlite3.Connection,
) -> None:
    """If no pending_review goal exists, Forward failure is a clean
    no-op (no spurious Strategist enqueue). Covers the case where
    Forward was Inject'd from T1 routine, not a T2 review event."""
    _insert_goal(conn, slug="main", origin="root", status="attempting")
    cascade_one(
        conn, pipeline_id="pid-fwd-noprev", kind="Forward",
        target_id="p", target_kind="Problem",
        outcome="failed", failure_reason="forward_no_new_goal",
    )
    q = conn.execute(
        "SELECT COUNT(*) AS n FROM queue WHERE kind='Strategist'"
    ).fetchone()
    assert q["n"] == 0


def test_t2_pops_before_bfs(
    conn: sqlite3.Connection,
) -> None:
    """A T2 (pending_review) Strategist enqueue must pop before any
    Backward / Builder BFS enqueue already in the queue. Regression
    guard: pre-fix, `_enqueue_strategist_review` omitted the priority
    kwarg and inherited db.enqueue default=0, putting T2 below
    Backward (=2) and Builder (=5) — inverting pipelines.md §2.1
    'T2 > T0 > T1' (and the §4.3 implied 'Strategist > Backward /
    Builder for pending review'). T2-vs-T0/T1 ordering is moot at
    runtime because per-problem Strategist dedup in
    `_enqueue_strategist_review` prevents simultaneous T0/T1+T2 rows
    for the same root."""
    root = _insert_goal(conn, slug="main", origin="root")
    sub = _insert_goal(conn, slug="sub", status="attempting")

    db.enqueue(conn, kind="Backward", target_id="999", priority=2)
    db.enqueue(conn, kind="Builder",  target_id="998", priority=5)
    _enqueue_strategist_review(conn, sub)

    first = db.pop_queue(conn)
    assert first is not None
    assert first["kind"] == "Strategist"
    assert first["priority"] == 20
    assert int(first["target_id"]) == root


# ---------------------------------------------------------------------
# Phase 2.5 — Inject batch completion hook
# ---------------------------------------------------------------------

def _seed_inject_batch_rows(conn: sqlite3.Connection, *,
                            problem: str = "p",
                            batch_id: str,
                            count: int) -> list[int]:
    ts = db.now()
    ids: list[int] = []
    for i in range(count):
        cur = conn.execute(
            "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
            " trigger_kind, decision_kind, target_id, brief, reason,"
            " payload, batch_id, outcome, created_at, updated_at)"
            " VALUES (?, 0, 'pending_review', 'Inject', NULL, ?, NULL,"
            "         ?, ?, NULL, ?, ?)",
            (problem, f"brief {i}",
             '{"pipeline":"Forward","step_index":' + str(i)
                + ',"batch_size":' + str(count) + '}',
             batch_id, ts, ts),
        )
        ids.append(int(cur.lastrowid))
    conn.commit()
    return ids


def test_batch_partial_completion_does_not_enqueue_strategist(
    conn: sqlite3.Connection,
) -> None:
    """2/3 Forwards done → no Strategist trigger yet. The hook only
    fires when EVERY decision row in the batch has outcome filled."""
    root = _insert_goal(conn, slug="main", origin="root", status="attempting")
    ids = _seed_inject_batch_rows(conn, batch_id="batch-x", count=3)

    cascade_one(conn, pipeline_id="pid1", kind="Forward",
                target_id="p", target_kind="Problem",
                outcome="success", decision_id=ids[0])
    cascade_one(conn, pipeline_id="pid2", kind="Forward",
                target_id="p", target_kind="Problem",
                outcome="failed", failure_reason="lake_build_error",
                decision_id=ids[1])
    # 1 row still pending → no Strategist enqueue
    q_strat = conn.execute(
        "SELECT COUNT(*) AS n FROM queue WHERE kind='Strategist'"
    ).fetchone()
    assert q_strat["n"] == 0
    # Outcomes recorded on the two done rows
    rows = list(conn.execute(
        "SELECT outcome FROM strategist_decisions"
        " WHERE batch_id='batch-x' ORDER BY id"
    ))
    assert rows[0]["outcome"] is not None
    assert rows[1]["outcome"] is not None
    assert rows[2]["outcome"] is None


def test_batch_full_completion_enqueues_one_strategist(
    conn: sqlite3.Connection,
) -> None:
    """All 3 Forwards done → exactly one Strategist enqueue with
    priority=20. Idempotent: a second cascade for the same batch must
    not double-enqueue (dedup via is_in_queue)."""
    root = _insert_goal(conn, slug="main", origin="root", status="attempting")
    ids = _seed_inject_batch_rows(conn, batch_id="batch-z", count=3)

    for pid, rid in zip(["p1", "p2", "p3"], ids):
        cascade_one(conn, pipeline_id=pid, kind="Forward",
                    target_id="p", target_kind="Problem",
                    outcome="success", decision_id=rid)

    q = list(conn.execute(
        "SELECT kind, target_id, priority FROM queue"
        " WHERE kind='Strategist'"
    ))
    assert len(q) == 1
    assert int(q[0]["target_id"]) == root
    assert q[0]["priority"] == 20

    # Re-fire cascade on the same last row (idempotent path); no second
    # enqueue. (`is_in_queue` blocks the duplicate.)
    cascade_one(conn, pipeline_id="p3-replay", kind="Forward",
                target_id="p", target_kind="Problem",
                outcome="success", decision_id=ids[-1])
    q2 = list(conn.execute(
        "SELECT COUNT(*) AS n FROM queue WHERE kind='Strategist'"
    ))
    assert q2[0]["n"] == 1


def test_batch_infra_failure_does_not_advance_completion(
    conn: sqlite3.Connection,
) -> None:
    """Infra outcomes (spawn_fast_fail / gateway_unreachable / quota_
    exhausted / transient_timeout / missing_dep) don't fill the batch
    row's outcome — those are transport failures, not the agent's
    Forward decision. Batch completion is not advanced; Strategist
    not enqueued."""
    _insert_goal(conn, slug="main", origin="root", status="attempting")
    ids = _seed_inject_batch_rows(conn, batch_id="batch-infra", count=2)

    cascade_one(conn, pipeline_id="pid1", kind="Forward",
                target_id="p", target_kind="Problem",
                outcome="failed", failure_reason="spawn_fast_fail",
                decision_id=ids[0])
    cascade_one(conn, pipeline_id="pid2", kind="Forward",
                target_id="p", target_kind="Problem",
                outcome="failed", failure_reason="gateway_unreachable",
                decision_id=ids[1])
    rows = list(conn.execute(
        "SELECT outcome FROM strategist_decisions"
        " WHERE batch_id='batch-infra'"
    ))
    assert all(r["outcome"] is None for r in rows)
    q = conn.execute(
        "SELECT COUNT(*) AS n FROM queue WHERE kind='Strategist'"
    ).fetchone()
    assert q["n"] == 0


def test_solo_inject_outcome_recorded_but_no_batch_trigger(
    conn: sqlite3.Connection,
) -> None:
    """Solo Inject (batch_id NULL): outcome still recorded on the
    decision row (useful for failure_replay) but the batch-done check
    is a no-op — no Strategist enqueue via the batch hook (the existing
    pending_review re-enqueue is a separate path)."""
    _insert_goal(conn, slug="main", origin="root", status="attempting")
    cur = conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, target_id, brief, reason, payload,"
        " batch_id, outcome, created_at, updated_at)"
        " VALUES ('p', 0, 'pending_review', 'Inject', NULL, 'solo',"
        "         NULL, '{}', NULL, NULL, ?, ?)",
        (db.now(), db.now()),
    )
    rid = int(cur.lastrowid)
    conn.commit()

    cascade_one(conn, pipeline_id="pidsolo", kind="Forward",
                target_id="p", target_kind="Problem",
                outcome="success", decision_id=rid)
    r = conn.execute(
        "SELECT outcome FROM strategist_decisions WHERE id = ?", (rid,)
    ).fetchone()
    assert r["outcome"] is not None
    q = conn.execute(
        "SELECT COUNT(*) AS n FROM queue WHERE kind='Strategist'"
    ).fetchone()
    assert q["n"] == 0


def test_unacknowledged_inject_batches_helper(
    conn: sqlite3.Connection,
) -> None:
    """db.unacknowledged_inject_batches returns batch_ids with all rows
    outcome-filled AND a row update newer than last_strategist_at."""
    _insert_goal(conn, slug="main", origin="root", status="attempting")
    ids_a = _seed_inject_batch_rows(conn, batch_id="batch-A", count=2)
    ids_b = _seed_inject_batch_rows(conn, batch_id="batch-B", count=2)

    # A fully done
    for rid in ids_a:
        conn.execute(
            "UPDATE strategist_decisions SET outcome='success', updated_at = ?"
            " WHERE id = ?", (db.now(), rid))
    # B half done
    conn.execute(
        "UPDATE strategist_decisions SET outcome='success', updated_at = ?"
        " WHERE id = ?", (db.now(), ids_b[0]))
    conn.commit()
    batches = db.unacknowledged_inject_batches(conn, "p")
    assert batches == ["batch-A"]

    # Advance last_strategist_at; batch A becomes acknowledged
    db.update_problem_last_strategist_at(conn, "p")
    batches2 = db.unacknowledged_inject_batches(conn, "p")
    assert batches2 == []
