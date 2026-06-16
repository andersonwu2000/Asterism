"""dispatcher.next_worker_kind + cascade_one state transitions."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from Tooling.state import db
from Tooling.core import dispatcher as _dispatcher
from Tooling.core.dispatcher import next_worker_kind, cascade_one, SHELVE_THRESHOLD


# ---------------------------------------------------------------------
# next_worker_kind
# ---------------------------------------------------------------------

def _fake_goal(*, attempts: int, entry_kind: str = "Builder") -> dict:
    return {"attempts": attempts, "entry_kind": entry_kind}


def test_next_worker_kind_honors_entry_kind_builder() -> None:
    """entry_kind='Builder' on a fresh goal routes to Builder regardless
    of any other signal — there's no longer a numeric `difficulty` gate
    that would override the directive."""
    assert next_worker_kind(
        _fake_goal(attempts=0, entry_kind="Builder")
    ) == "Builder"


def test_next_worker_kind_honors_entry_kind_backward() -> None:
    """entry_kind='Backward' on a fresh goal skips Builder entirely."""
    assert next_worker_kind(
        _fake_goal(attempts=0, entry_kind="Backward")
    ) == "Backward"


def test_next_worker_kind_easy_first_attempts() -> None:
    assert next_worker_kind(
        _fake_goal(attempts=0)) == "Builder"
    assert next_worker_kind(
        _fake_goal(attempts=2)) == "Builder"


def test_next_worker_kind_boundary_at_builder_threshold() -> None:
    """attempts >= BUILDER_THRESHOLD overrides entry_kind=Builder
    (safety net): the Backward agent's directive can be wrong, but
    after N consecutive Builder failures we escalate regardless."""
    bt = _dispatcher.BUILDER_THRESHOLD
    assert next_worker_kind(
        _fake_goal(attempts=bt - 1)) == "Builder"
    assert next_worker_kind(
        _fake_goal(attempts=bt)) == "Backward"
    # Even with entry_kind=Builder, attempts threshold wins
    assert next_worker_kind(
        _fake_goal(attempts=bt, entry_kind="Builder")
    ) == "Backward"


def test_next_worker_kind_respects_runtime_threshold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F18: BUILDER_THRESHOLD is module-level mutable so env override
    in `run` takes effect without re-import. Direct assignment is the
    same channel."""
    monkeypatch.setattr(_dispatcher, "BUILDER_THRESHOLD", 3)
    assert next_worker_kind(
        _fake_goal(attempts=2)) == "Builder"
    assert next_worker_kind(
        _fake_goal(attempts=3)) == "Backward"


# ---------------------------------------------------------------------
# Threshold defaults — single (3, 8) baseline.
# F31's haiku-substring tier was retired alongside the Asterism.yaml
# config introduction: weak-tier users now write `builder.threshold:
# 5` + `dispatch.shelve_threshold: 10` explicitly. F47 moved
# builder_threshold from dispatch.* to builder.* (kind-local); the
# legacy yaml key stays honored as a fallback. Tested via test_config.
# ---------------------------------------------------------------------

def test_threshold_defaults_are_strong_tier() -> None:
    """Module-level constants reflect the post-substring-removal default."""
    assert _dispatcher.BUILDER_THRESHOLD == 3
    assert _dispatcher.SHELVE_THRESHOLD == 8


# ---------------------------------------------------------------------
# cascade_one — Builder
# ---------------------------------------------------------------------

def _seed_goal(conn: sqlite3.Connection, *, problem: str = "p") -> int:
    conn.execute(
        "INSERT INTO problems (name, manifest_path, created_at, bootstrap_done) VALUES (?, ?, ?, 1)",
        (problem, "Problems/p/Manifest.md", db.now()),
    )
    return db.insert_goal(
        conn, problem=problem, slug="main", lean_path="Problems/p/Root.lean",
        statement="T", origin="root",
    )


def test_cascade_builder_proved(conn: sqlite3.Connection) -> None:
    gid = _seed_goal(conn)
    cascade_one(conn, pipeline_id="pid", kind="Builder",
                target_id=str(gid), target_kind="Goal", outcome="proved")
    row = db.get_goal(conn, gid)
    assert row["status"] == "proved"


def test_cascade_builder_failed_increments_attempts(conn: sqlite3.Connection) -> None:
    gid = _seed_goal(conn)
    cascade_one(conn, pipeline_id="pid", kind="Builder",
                target_id=str(gid), target_kind="Goal", outcome="failed")
    row = db.get_goal(conn, gid)
    assert row["attempts"] == 1
    assert row["status"] == "open"


def test_cascade_builder_at_threshold_routes_to_pending_review(
    conn: sqlite3.Connection,
) -> None:
    """After SHELVE_THRESHOLD attempts, the goal is no longer auto-
    shelved — it transitions to `pending_strategist_review` so the
    Strategist gets to commit ConfirmShelve / Reopen / Inject /
    EmitDirective / RequestUserAmend with full goal context. Mirrors
    the agent_shelved escalation path. Orphan-chain fallback (auto
    `shelved` when no live ancestor strategy exists) is exercised
    separately."""
    gid = _seed_goal(conn)
    for _ in range(SHELVE_THRESHOLD):
        cascade_one(conn, pipeline_id="pid", kind="Builder",
                    target_id=str(gid), target_kind="Goal", outcome="failed")
    row = db.get_goal(conn, gid)
    assert row["status"] == "pending_strategist_review"
    assert row["attempts"] == SHELVE_THRESHOLD


# ---------------------------------------------------------------------
# Phase 7-D — DROP migration for retired session_id columns
# ---------------------------------------------------------------------

def test_db_migration_drops_legacy_session_id_columns(
    tmp_path: Path,
) -> None:
    """Older DBs created with the former cross-pipeline session_id
    columns (builder_session_id / backward_session_id, retired
    Phase 7-D) must have those columns dropped by init_schema's
    idempotent migration. New DBs created from the current SCHEMA
    don't have them in the first place; the migration's "no such
    column" branch covers both cases."""
    import sqlite3 as _sq
    db_path = tmp_path / "legacy.db"
    legacy = _sq.connect(str(db_path))
    legacy.executescript("""
        CREATE TABLE problems (
            name TEXT PRIMARY KEY,
            manifest_path TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            problem TEXT NOT NULL REFERENCES problems(name),
            slug TEXT NOT NULL,
            lean_path TEXT NOT NULL UNIQUE,
            statement TEXT NOT NULL,
            kind TEXT NOT NULL DEFAULT 'theorem' CHECK(kind IN ('theorem')),
            origin TEXT NOT NULL CHECK(origin IN ('root','backward')),
            status TEXT NOT NULL CHECK(status IN ('open','attempting','proved','shelved')),
            depth INTEGER NOT NULL DEFAULT 0,
            attempts INTEGER NOT NULL DEFAULT 0,
            builder_session_id TEXT NULL DEFAULT NULL,
            backward_session_id TEXT NULL DEFAULT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(problem, slug)
        );
    """)
    legacy.commit()
    legacy.close()

    fresh = _sq.connect(str(db_path))
    fresh.row_factory = _sq.Row
    db.init_schema(fresh)
    cols = [r[1] for r in fresh.execute("PRAGMA table_info(goals)").fetchall()]
    assert "builder_session_id" not in cols
    assert "backward_session_id" not in cols
    # Idempotent: re-running init_schema on the now-clean DB is a no-op.
    db.init_schema(fresh)
    fresh.close()


# ---------------------------------------------------------------------
# cascade_one — Backward
# ---------------------------------------------------------------------

def test_cascade_backward_success_marks_attempting(conn: sqlite3.Connection) -> None:
    gid = _seed_goal(conn)
    # Seed a live strategy so the success cascade has something to
    # attribute the 'attempting' transition to. Without it, the
    # has_live race guard would (correctly) skip the transition; that
    # path is exercised by the no-live-strategy regression test below.
    db.insert_strategy(
        conn, goal_id=gid, lean_path="Problems/p/Root.lean",
        created_by="pid", proposal_md="", scratch_path="",
    )
    cascade_one(conn, pipeline_id="pid", kind="Backward",
                target_id=str(gid), target_kind="Goal", outcome="success")
    row = db.get_goal(conn, gid)
    assert row["status"] == "attempting"


def test_cascade_backward_success_no_live_strategy_preserves_status(
    conn: sqlite3.Connection,
) -> None:
    """Race guard regression: when verify_housekeeping fires before a
    Backward 'success' cascade and kills the just-committed strategy
    (e.g. leaf-bypass with sorry-stub body → axiom_violation → strategy
    dead → goal reopened to 'open'), the late-arriving cascade must NOT
    overwrite the verify-set status with 'attempting'. Pre-fix
    behavior: cascade unconditionally set 'attempting', leaving the goal
    in a self-inconsistent state (no live strategy yet status=
    'attempting'); bfs_refill's open-only filter then excluded it and
    the dispatcher idle-exited even though attempts budget remained.
    Observed SG run #3 root goal 232 — exit at attempts=2 with
    shelve_threshold=5, 3 retries left unused."""
    gid = _seed_goal(conn)
    # Seed a strategy that mirrors the post-verify state: dead, no
    # other live strategy on this goal. verify would have already
    # transitioned the goal back to 'open' by this point.
    sid = db.insert_strategy(
        conn, goal_id=gid, lean_path="Problems/p/Root.lean",
        created_by="pid", proposal_md="", scratch_path="",
    )
    db.update_strategy_status(conn, sid, "dead")
    db.update_goal_status(conn, gid, "open")
    # Late cascade arrives.
    cascade_one(conn, pipeline_id="pid", kind="Backward",
                target_id=str(gid), target_kind="Goal", outcome="success")
    row = db.get_goal(conn, gid)
    assert row["status"] == "open", (
        f"Backward 'success' cascade with no live strategy must not "
        f"clobber verify-set status; got {row['status']!r}"
    )


def test_cascade_backward_failed_increments(conn: sqlite3.Connection) -> None:
    gid = _seed_goal(conn)
    cascade_one(conn, pipeline_id="pid", kind="Backward",
                target_id=str(gid), target_kind="Goal", outcome="failed")
    row = db.get_goal(conn, gid)
    assert row["attempts"] == 1


# ---------------------------------------------------------------------
# F12 — sub-goal shelve propagates to parent strategies
# ---------------------------------------------------------------------

def test_subgoal_at_threshold_routes_to_pending_review(
    conn: sqlite3.Connection,
) -> None:
    """Sub-goal hitting SHELVE_THRESHOLD via repeated failures now
    transitions to `pending_strategist_review` (not auto `shelved`).
    Parent strategy stays 'proposed' (Strategist decides whether to
    ConfirmShelve / Reopen / Inject); grandparent stays attempting
    until Strategist acts. Distinct from disproved / dead which
    kill the upward chain unconditionally."""
    grand = _seed_goal(conn, problem="p")
    db.update_goal_status(conn, grand, "attempting")

    doomed_sub = db.insert_goal(
        conn, problem="p", slug="doomed_sub",
        lean_path="Problems/p/proofs/L_doomed_sub.lean",
        statement="T", origin="backward", depth=1,
    )

    sid = db.insert_strategy(
        conn, goal_id=grand,
        lean_path="Problems/p/Root.lean",
        scratch_path="Problems/p/proofs/_strategy_s.lean",
        created_by="pid",
    )
    db.link_subgoal(conn, strategy_id=sid, subgoal_id=doomed_sub, position=0)

    for _ in range(SHELVE_THRESHOLD):
        cascade_one(conn, pipeline_id="pid", kind="Builder",
                    target_id=str(doomed_sub), target_kind="Goal",
                    outcome="failed")

    assert db.get_goal(conn, doomed_sub)["status"] == "pending_strategist_review"
    # Parent strategy stays 'proposed' (Strategist may Reopen later)
    assert conn.execute(
        "SELECT status FROM strategies WHERE id = ?", (sid,),
    ).fetchone()["status"] == "proposed"
    # Grandparent stays attempting (not auto-reopened) — Strategist or
    # operator must intervene to break the wait
    assert db.get_goal(conn, grand)["status"] == "attempting"


def test_parent_needs_fix_kills_upward_chain_phase6(
    conn: sqlite3.Connection,
) -> None:
    """Phase 6: `parent_needs_fix` decline flips goal to status='dead'
    (parent strategy was wrong, this goal moot in that context) AND
    triggers upward strategy kill. Replaces the legacy shelve-as-cascade
    pattern from pre-Phase-6 tests.
    """
    grand = _seed_goal(conn, problem="p")
    db.update_goal_status(conn, grand, "attempting")

    sub = db.insert_goal(
        conn, problem="p", slug="needs_fix_sub",
        lean_path="Problems/p/proofs/L_needs_fix_sub.lean",
        statement="T", origin="backward", depth=1,
    )
    sid = db.insert_strategy(
        conn, goal_id=grand,
        lean_path="Problems/p/Root.lean",
        scratch_path="Problems/p/proofs/_strategy_s.lean",
        created_by="pid",
    )
    db.link_subgoal(conn, strategy_id=sid, subgoal_id=sub, position=0)

    cascade_one(conn, pipeline_id="pid", kind="Builder",
                target_id=str(sub), target_kind="Goal", outcome="failed",
                failure_reason="parent_needs_fix")

    assert db.get_goal(conn, sub)["status"] == "dead"
    assert conn.execute(
        "SELECT status FROM strategies WHERE id = ?", (sid,),
    ).fetchone()["status"] == "dead"
    # Grandparent reopened so Backward can propose a different strategy
    assert db.get_goal(conn, grand)["status"] == "open"
    assert db.get_goal(conn, grand)["attempts"] == 1


def test_parent_needs_fix_cascades_grand_when_at_threshold(
    conn: sqlite3.Connection,
) -> None:
    """Phase 6: parent_needs_fix on sub-goal flips it to 'dead' AND kills
    upward strategy. If the grand's attempts increment from this cascade
    crosses SHELVE_THRESHOLD, grand also flips to 'dead' (mirrors what
    happens up the chain — wrong context propagates)."""
    grand = _seed_goal(conn, problem="p")
    db.update_goal_status(conn, grand, "attempting")
    conn.execute("UPDATE goals SET attempts = ? WHERE id = ?",
                 (SHELVE_THRESHOLD - 1, grand))
    conn.commit()

    sub = db.insert_goal(
        conn, problem="p", slug="needs_fix_grand",
        lean_path="Problems/p/proofs/L_needs_fix_grand.lean",
        statement="T", origin="backward", depth=1,
    )
    sid = db.insert_strategy(
        conn, goal_id=grand,
        lean_path="Problems/p/Root.lean",
        scratch_path="Problems/p/proofs/_strategy_grand.lean",
        created_by="pid",
    )
    db.link_subgoal(conn, strategy_id=sid, subgoal_id=sub, position=0)

    cascade_one(conn, pipeline_id="pid", kind="Builder",
                target_id=str(sub), target_kind="Goal", outcome="failed",
                failure_reason="parent_needs_fix")

    assert db.get_goal(conn, sub)["status"] == "dead"
    assert db.get_goal(conn, grand)["status"] == "dead"
    assert db.get_goal(conn, grand)["attempts"] == SHELVE_THRESHOLD


def test_parent_needs_fix_keeps_goal_attempting_when_other_strategy_alive(
    conn: sqlite3.Connection,
) -> None:
    """parent_needs_fix kills only the strategy that produced the dead
    sub-goal. Sibling strategies on the grandparent stay alive and the
    grandparent does NOT reopen (would displace a working sibling), but
    attempts MUST still increment — the cascade carried a strong signal
    (a descendant repudiated this decomposition), and silently dropping
    it lets SHELVE_THRESHOLD never fire on goals stuck around a long-
    lived but unviable sibling."""
    grand = _seed_goal(conn, problem="p")
    db.update_goal_status(conn, grand, "attempting")

    sub = db.insert_goal(
        conn, problem="p", slug="needs_fix_sibling",
        lean_path="Problems/p/proofs/L_needs_fix_sibling.lean",
        statement="T", origin="backward", depth=1,
    )

    # Two strategies on grand; only s1 includes sub
    s1 = db.insert_strategy(conn, goal_id=grand,
                            lean_path="Problems/p/Root.lean",
                            scratch_path="Problems/p/proofs/_strategy_s1.lean",
                            created_by="pid1")
    db.link_subgoal(conn, strategy_id=s1, subgoal_id=sub, position=0)

    s2 = db.insert_strategy(conn, goal_id=grand,
                            lean_path="Problems/p/Root.lean",
                            scratch_path="Problems/p/proofs/_strategy_s2.lean",
                            created_by="pid2")

    cascade_one(conn, pipeline_id="pid", kind="Builder",
                target_id=str(sub), target_kind="Goal", outcome="failed",
                failure_reason="parent_needs_fix")

    assert conn.execute(
        "SELECT status FROM strategies WHERE id = ?", (s1,),
    ).fetchone()["status"] == "dead"
    assert conn.execute(
        "SELECT status FROM strategies WHERE id = ?", (s2,),
    ).fetchone()["status"] == "proposed"
    assert db.get_goal(conn, grand)["status"] == "attempting"
    assert db.get_goal(conn, grand)["attempts"] == 1
    assert s2  # silence unused warning


def test_cascade_at_threshold_with_sibling_alive_defers_terminal(
    conn: sqlite3.Connection,
) -> None:
    """When a cascade strong-signal would tip SHELVE_THRESHOLD but a
    sibling strategy is still in flight (e.g. Strategist parallel
    inject), terminal shelving is deferred — attempts still records the
    failure, but we don't kill the working sibling. The deferred
    terminal fires later when that sibling's own cascade arrives with
    no live siblings remaining.
    """
    grand = _seed_goal(conn, problem="p")
    db.update_goal_status(conn, grand, "attempting")
    # Pre-load attempts so one more cascade tips threshold.
    conn.execute("UPDATE goals SET attempts = ? WHERE id = ?",
                 (SHELVE_THRESHOLD - 1, grand))
    conn.commit()

    # In-flight sibling — represents a parallel-inject worker that
    # must NOT be killed by the threshold-induced shelve.
    sibling = db.insert_strategy(
        conn, goal_id=grand,
        lean_path="Problems/p/Root.lean",
        scratch_path="Problems/p/proofs/_strategy_sibling.lean",
        created_by="pid_sib",
    )

    sub = db.insert_goal(
        conn, problem="p", slug="failing_sub",
        lean_path="Problems/p/proofs/L_failing_sub.lean",
        statement="T", origin="backward", depth=1,
    )
    s_failing = db.insert_strategy(
        conn, goal_id=grand,
        lean_path="Problems/p/Root.lean",
        scratch_path="Problems/p/proofs/_strategy_failing.lean",
        created_by="pid_fail",
    )
    db.link_subgoal(conn, strategy_id=s_failing, subgoal_id=sub, position=0)

    cascade_one(conn, pipeline_id="pid", kind="Builder",
                target_id=str(sub), target_kind="Goal", outcome="failed",
                failure_reason="parent_needs_fix")

    # Failing strategy killed, sub dead, attempts at threshold — but
    # sibling untouched and grand still 'attempting' (deferred).
    assert db.get_goal(conn, sub)["status"] == "dead"
    assert conn.execute(
        "SELECT status FROM strategies WHERE id = ?", (s_failing,),
    ).fetchone()["status"] == "dead"
    assert conn.execute(
        "SELECT status FROM strategies WHERE id = ?", (sibling,),
    ).fetchone()["status"] == "proposed"
    grand_row = db.get_goal(conn, grand)
    assert grand_row["status"] == "attempting"
    assert grand_row["attempts"] == SHELVE_THRESHOLD


def test_deferred_terminal_fires_when_last_sibling_dies(
    conn: sqlite3.Connection,
) -> None:
    """After a threshold-deferred shelve, when the protecting sibling
    itself dies via cascade the next _kill_upward_chain pass sees
    has_live=False and attempts >= SHELVE_THRESHOLD → terminal fires.
    """
    grand = _seed_goal(conn, problem="p")
    db.update_goal_status(conn, grand, "attempting")
    conn.execute("UPDATE goals SET attempts = ? WHERE id = ?",
                 (SHELVE_THRESHOLD - 1, grand))
    conn.commit()

    # Two strategies, each owning its own subgoal so we can cascade
    # them independently.
    sub_a = db.insert_goal(
        conn, problem="p", slug="sub_a",
        lean_path="Problems/p/proofs/L_sub_a.lean",
        statement="T", origin="backward", depth=1,
    )
    s_a = db.insert_strategy(
        conn, goal_id=grand,
        lean_path="Problems/p/Root.lean",
        scratch_path="Problems/p/proofs/_strategy_a.lean",
        created_by="pid_a",
    )
    db.link_subgoal(conn, strategy_id=s_a, subgoal_id=sub_a, position=0)

    sub_b = db.insert_goal(
        conn, problem="p", slug="sub_b",
        lean_path="Problems/p/proofs/L_sub_b.lean",
        statement="T", origin="backward", depth=1,
    )
    s_b = db.insert_strategy(
        conn, goal_id=grand,
        lean_path="Problems/p/Root.lean",
        scratch_path="Problems/p/proofs/_strategy_b.lean",
        created_by="pid_b",
    )
    db.link_subgoal(conn, strategy_id=s_b, subgoal_id=sub_b, position=0)

    # First cascade: tips threshold, sibling s_b still alive → defer.
    cascade_one(conn, pipeline_id="pid_a", kind="Builder",
                target_id=str(sub_a), target_kind="Goal", outcome="failed",
                failure_reason="parent_needs_fix")
    assert db.get_goal(conn, grand)["status"] == "attempting"
    assert conn.execute(
        "SELECT status FROM strategies WHERE id = ?", (s_b,),
    ).fetchone()["status"] == "proposed"

    # Second cascade: kills s_b, no live sibling, attempts already past
    # threshold → terminal fires (parent_terminal_status='dead').
    cascade_one(conn, pipeline_id="pid_b", kind="Builder",
                target_id=str(sub_b), target_kind="Goal", outcome="failed",
                failure_reason="parent_needs_fix")
    assert conn.execute(
        "SELECT status FROM strategies WHERE id = ?", (s_b,),
    ).fetchone()["status"] == "dead"
    assert db.get_goal(conn, grand)["status"] == "dead"


def test_reconcile_after_placeholder_delete_reopens_under_threshold(
    conn: sqlite3.Connection,
) -> None:
    """When a worker-Exception placeholder deletion leaves a goal with
    no live strategy and attempts < SHELVE_THRESHOLD, the reconciler
    reopens the goal so bfs_refill can dispatch a fresh Backward.
    Without this, the goal sits 'attempting' indefinitely until the
    next daemon restart's recovery sweep.
    """
    from Tooling.core.dispatcher import _reconcile_goal_after_strategy_loss
    grand = _seed_goal(conn, problem="p")
    db.update_goal_status(conn, grand, "attempting")
    db.increment_goal_attempts(conn, grand)  # attempts = 1, below threshold

    # Simulate post-deletion state: goal has no live strategy.
    _reconcile_goal_after_strategy_loss(conn, grand)

    assert db.get_goal(conn, grand)["status"] == "open"


def test_reconcile_after_placeholder_delete_routes_to_pending_review_at_threshold(
    conn: sqlite3.Connection,
) -> None:
    """If accumulated deferred-cascade attempts already crossed
    SHELVE_THRESHOLD, the reconciler routes the goal to
    `pending_strategist_review` (was: auto-shelve). Strategist decides
    final disposition."""
    from Tooling.core.dispatcher import _reconcile_goal_after_strategy_loss
    grand = _seed_goal(conn, problem="p")
    db.update_goal_status(conn, grand, "attempting")
    conn.execute("UPDATE goals SET attempts = ? WHERE id = ?",
                 (SHELVE_THRESHOLD, grand))
    conn.commit()

    _reconcile_goal_after_strategy_loss(conn, grand)

    assert db.get_goal(conn, grand)["status"] == "pending_strategist_review"


def test_reconcile_noop_when_sibling_alive(
    conn: sqlite3.Connection,
) -> None:
    """Reconciler does nothing if the goal still has any live strategy
    — the deletion left other siblings in play, normal flow applies."""
    from Tooling.core.dispatcher import _reconcile_goal_after_strategy_loss
    grand = _seed_goal(conn, problem="p")
    db.update_goal_status(conn, grand, "attempting")
    db.insert_strategy(
        conn, goal_id=grand,
        lean_path="Problems/p/Root.lean",
        scratch_path="Problems/p/proofs/_strategy_alive.lean",
        created_by="pid",
    )

    _reconcile_goal_after_strategy_loss(conn, grand)

    assert db.get_goal(conn, grand)["status"] == "attempting"


def test_strategies_ready_for_verify_excludes_shelved_goal(
    conn: sqlite3.Connection,
) -> None:
    """F12 secondary fix: defensive — strategies on shelved goals must
    not be returned as ready_for_verify (their parent is dead)."""
    gid = _seed_goal(conn)
    sub = db.insert_goal(
        conn, problem="p", slug="proved_sub_x",
        lean_path="Problems/p/proofs/L_proved_sub_x.lean",
        statement="T", origin="backward", depth=1,
    )
    db.update_goal_status(conn, sub, "proved")
    sid = db.insert_strategy(conn, goal_id=gid,
                             lean_path="Problems/p/Root.lean",
                             scratch_path="Problems/p/proofs/_strategy_x.lean",
                             created_by="pid")
    db.link_subgoal(conn, strategy_id=sid, subgoal_id=sub, position=0)

    # Initially: ready
    assert any(s["id"] == sid for s in db.strategies_ready_for_verify(conn))

    # Shelve the goal
    db.update_goal_status(conn, gid, "shelved")
    assert not any(s["id"] == sid
                   for s in db.strategies_ready_for_verify(conn))


# ---------------------------------------------------------------------
# F24 — cascade no-op guards on shelved goal (defense vs OR-race)
# ---------------------------------------------------------------------

def test_cascade_builder_failed_on_shelved_goal_is_noop(
    conn: sqlite3.Connection,
) -> None:
    """Late Builder pipeline finishes after the goal already shelved.
    Cascade must not bump attempts further or mutate status."""
    gid = _seed_goal(conn)
    db.update_goal_status(conn, gid, "shelved")
    # Push attempts to a known value to prove no further increment
    conn.execute("UPDATE goals SET attempts = 8 WHERE id = ?", (gid,))
    conn.commit()

    cascade_one(conn, pipeline_id="late", kind="Builder",
                target_id=str(gid), target_kind="Goal", outcome="failed")

    row = conn.execute(
        "SELECT status, attempts FROM goals WHERE id = ?", (gid,),
    ).fetchone()
    assert row["status"] == "shelved"
    assert row["attempts"] == 8


def test_cascade_backward_succeeded_on_shelved_goal_does_not_unshelve(
    conn: sqlite3.Connection,
) -> None:
    """Reverse-test of the observed race: a Backward 'success' that
    arrives after the goal was shelved must NOT flip status back to
    'attempting'. The strategy that Backward already wrote becomes a
    DB-side concern (handled by run_backward's own race guard)."""
    gid = _seed_goal(conn)
    db.update_goal_status(conn, gid, "shelved")
    conn.execute("UPDATE goals SET attempts = 8 WHERE id = ?", (gid,))
    conn.commit()

    cascade_one(conn, pipeline_id="late_backward", kind="Backward",
                target_id=str(gid), target_kind="Goal", outcome="success")

    row = conn.execute(
        "SELECT status, attempts FROM goals WHERE id = ?", (gid,),
    ).fetchone()
    assert row["status"] == "shelved"
    assert row["attempts"] == 8


def test_cascade_strategy_on_shelved_parent_marks_dead(
    conn: sqlite3.Connection,
) -> None:
    """Strategy whose parent goal got shelved while this strategy's
    Verify was in flight: cascade must mark strategy dead so the
    `proposed → parent alive` invariant holds."""
    gid = _seed_goal(conn)
    sid = db.insert_strategy(conn, goal_id=gid,
                             lean_path="Problems/p/Root.lean",
                             scratch_path="Problems/p/proofs/_strategy_x.lean",
                             created_by="pid")
    db.update_goal_status(conn, gid, "shelved")

    cascade_one(conn, pipeline_id="pid", kind="Verify",
                target_id=str(sid), target_kind="Strategy",
                outcome="failed")

    row = conn.execute(
        "SELECT status FROM strategies WHERE id = ?", (sid,),
    ).fetchone()
    assert row["status"] == "dead"
    # Goal still shelved
    assert db.get_goal(conn, gid)["status"] == "shelved"



# ---------------------------------------------------------------------
# F16 — at SHELVE_THRESHOLD, goal routes to pending_strategist_review
# (was: auto-shelve with strategy kill). Strategies stay alive while
# the goal is transitional, since Strategist may Reopen.
# ---------------------------------------------------------------------

def test_goal_at_threshold_preserves_own_strategies(
    conn: sqlite3.Connection,
) -> None:
    """B-1 (linalg series 2026-05-23 followup): after SHELVE_THRESHOLD
    failures, the goal transitions to `pending_strategist_review`,
    NOT `shelved`. Its own strategies stay 'proposed' because the
    goal isn't terminal yet — Strategist may Reopen, in which case
    those strategies are still useful. Cascade-shelve of own
    strategies only fires when Strategist commits a true ConfirmShelve."""
    gid = _seed_goal(conn)

    s1 = db.insert_strategy(conn, goal_id=gid,
                            lean_path="Problems/p/Root.lean",
                            scratch_path="Problems/p/proofs/_strategy_a.lean",
                            created_by="pid1")
    s2 = db.insert_strategy(conn, goal_id=gid,
                            lean_path="Problems/p/Root.lean",
                            scratch_path="Problems/p/proofs/_strategy_b.lean",
                            created_by="pid2")

    for _ in range(SHELVE_THRESHOLD):
        cascade_one(conn, pipeline_id="pid", kind="Backward",
                    target_id=str(gid), target_kind="Goal",
                    outcome="failed")

    assert db.get_goal(conn, gid)["status"] == "pending_strategist_review"
    # Strategies stay alive (parent not terminal yet).
    for sid in (s1, s2):
        assert conn.execute(
            "SELECT status FROM strategies WHERE id = ?", (sid,),
        ).fetchone()["status"] == "proposed"


def test_dead_goal_combined_upward_and_inward_cascade(
    conn: sqlite3.Connection,
) -> None:
    """Phase 6: a goal that is both (a) sub-goal of a parent strategy
    and (b) has its own strategies, when flipped to 'dead' (via
    parent_needs_fix), kills strategies in BOTH directions —
    upward (the parent strategy that built on this goal) and inward
    (this goal's own strategies, now moot)."""
    grand = _seed_goal(conn, problem="p")
    db.update_goal_status(conn, grand, "attempting")

    middle = db.insert_goal(
        conn, problem="p", slug="middle",
        lean_path="Problems/p/proofs/L_middle.lean",
        statement="T", origin="backward", depth=1,
    )

    # parent strategy of grand uses middle as sub-goal
    parent_strat = db.insert_strategy(
        conn, goal_id=grand,
        lean_path="Problems/p/Root.lean",
        scratch_path="Problems/p/proofs/_strategy_p.lean",
        created_by="pid_p",
    )
    db.link_subgoal(conn, strategy_id=parent_strat,
                    subgoal_id=middle, position=0)

    # middle has its own strategy too
    own_strat = db.insert_strategy(
        conn, goal_id=middle,
        lean_path="Problems/p/proofs/L_middle.lean",
        scratch_path="Problems/p/proofs/_strategy_m.lean",
        created_by="pid_m",
    )

    cascade_one(conn, pipeline_id="pid", kind="Backward",
                target_id=str(middle), target_kind="Goal", outcome="failed",
                failure_reason="parent_needs_fix")

    # parent strategy killed (built on a now-dead goal)
    assert conn.execute(
        "SELECT status FROM strategies WHERE id = ?", (parent_strat,),
    ).fetchone()["status"] == "dead"
    # middle's own strategy killed (its goal is terminal)
    assert conn.execute(
        "SELECT status FROM strategies WHERE id = ?", (own_strat,),
    ).fetchone()["status"] == "dead"
    # grand reopened (no live strategy)
    assert db.get_goal(conn, grand)["status"] == "open"


# F56 — cascade_one no longer handles kind="Verify"; strategy state
# transitions are owned by `verify.verify_housekeeping`. See
# `tests/test_verify.py` for the equivalent coverage.


# ---------------------------------------------------------------------
# OR parallelism (W5/C)
# ---------------------------------------------------------------------

def test_two_strategies_share_parent_lean_path(conn: sqlite3.Connection) -> None:
    """Drop of UNIQUE on strategies.lean_path: multiple strategies can
    coexist for the same parent goal."""
    gid = _seed_goal(conn)
    sid1 = db.insert_strategy(conn, goal_id=gid,
                              lean_path="Problems/p/Root.lean",
                              created_by="pid-1")
    sid2 = db.insert_strategy(conn, goal_id=gid,
                              lean_path="Problems/p/Root.lean",
                              created_by="pid-2")
    assert sid1 != sid2


def test_cascade_no_op_when_goal_already_proved(
    conn: sqlite3.Connection,
) -> None:
    """Late-arriving Builder/Backward result on a proved goal is silent."""
    gid = _seed_goal(conn)
    db.update_goal_status(conn, gid, "proved")
    cascade_one(conn, pipeline_id="late", kind="Builder",
                target_id=str(gid), target_kind="Goal", outcome="failed")
    g = db.get_goal(conn, gid)
    assert g["status"] == "proved"  # not touched
    assert g["attempts"] == 0       # not incremented


def test_cascade_no_op_when_strategy_superseded(
    conn: sqlite3.Connection,
) -> None:
    gid = _seed_goal(conn)
    sid = db.insert_strategy(conn, goal_id=gid,
                             lean_path="Problems/p/Root.lean",
                             created_by="pid")
    db.update_strategy_status(conn, sid, "superseded")
    cascade_one(conn, pipeline_id="late", kind="Verify",
                target_id=str(sid), target_kind="Strategy", outcome="proved")
    s = conn.execute("SELECT status FROM strategies WHERE id = ?",
                     (sid,)).fetchone()
    assert s["status"] == "superseded"  # cascade did not flip to succeeded


def test_open_goals_filters_orphan_subgoals(conn: sqlite3.Connection) -> None:
    """A backward-origin sub-goal whose parent strategy is 'superseded'
    must be excluded from open_goals."""
    parent_gid = _seed_goal(conn)
    sid = db.insert_strategy(conn, goal_id=parent_gid,
                             lean_path="Problems/p/Root.lean",
                             created_by="pid")
    sub_gid = db.insert_goal(
        conn, problem="p", slug="orphan_sub",
        lean_path="Problems/p/proofs/L_orphan_sub.lean",
        statement="T", origin="backward", depth=1,
    )
    db.link_subgoal(conn, strategy_id=sid, subgoal_id=sub_gid, position=0)

    # Initially: parent strategy alive → sub-goal eligible
    ids = [g["id"] for g in db.open_goals(conn)]
    assert sub_gid in ids

    # Mark strategy superseded → sub-goal becomes orphan
    db.update_strategy_status(conn, sid, "superseded")
    ids = [g["id"] for g in db.open_goals(conn)]
    assert sub_gid not in ids
    assert parent_gid in ids  # root unaffected


def test_recover_at_startup_clears_queue(conn: sqlite3.Connection) -> None:
    from Tooling.core.dispatcher import _recover_at_startup
    db.enqueue(conn, kind="Backward", target_id="42")
    db.enqueue(conn, kind="Verify", target_id="9")
    _recover_at_startup(conn)
    assert db.queue_count(conn, target_id="42", kind="Backward") == 0
    assert db.queue_count(conn, target_id="9", kind="Verify") == 0


def test_recover_at_startup_sweeps_stale_migrate_probes(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """#104 — crash-orphan Library/_migrate_probe_* (the Librarian Gate B
    verify temp, normally unlinked in a finally, leaked by a hard kill)
    are swept at startup; real Library files stay untouched."""
    from Tooling.core.dispatcher import _recover_at_startup
    libdir = tmp_path / "Library"
    (libdir / "LinearAlgebra").mkdir(parents=True)
    probe1 = libdir / "_migrate_probe_abc123.lean"
    probe2 = libdir / "_migrate_probe_def456.lean"
    index = libdir / "INDEX.md"
    real_lean = libdir / "LinearAlgebra" / "SVD.lean"
    for f, body in ((probe1, "-- probe\n"), (probe2, "-- probe\n"),
                    (index, "# index\n"),
                    (real_lean, "theorem t : True := trivial\n")):
        f.write_text(body, encoding="utf-8")

    _recover_at_startup(conn, tmp_path)

    assert not probe1.exists()
    assert not probe2.exists()
    assert index.exists()        # real Library file untouched
    assert real_lean.exists()    # nested real file untouched


def test_recover_at_startup_sweeps_orphan_proof_files(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """Orphan proof files (on disk, NO DB row) from a Backward placement
    that died before its goal-row commit are reconciled at startup:
    uncited orphans (L_ and _strategy_) deleted; goal-backed files kept;
    a CITED orphan kept (deleting it would break the importer) — the
    already-propagated fake-proof case that needs explicit repair."""
    from Tooling.core.dispatcher import _recover_at_startup
    conn.execute(
        "INSERT INTO problems (name, manifest_path, created_at,"
        " bootstrap_done) VALUES ('p', 'Problems/p/Manifest.md', ?, 1)",
        (db.now(),))
    db.insert_goal(
        conn, problem="p", slug="real_lemma",
        lean_path="Problems/p/proofs/L_real_lemma.lean",
        statement="T", origin="backward", status="proved")
    conn.commit()

    proofs = tmp_path / "Problems" / "p" / "proofs"
    proofs.mkdir(parents=True)
    real = proofs / "L_real_lemma.lean"
    cited = proofs / "L_cited_orphan.lean"
    uncited = proofs / "L_uncited_orphan.lean"
    orphan_strat = proofs / "_strategy_s99999.lean"
    # The real (goal-backed) file imports the cited orphan.
    real.write_text(
        "import Problems.p.proofs.L_cited_orphan\n"
        "theorem real_lemma : True := trivial\n", encoding="utf-8")
    cited.write_text(
        "theorem cited_orphan : True := by sorry\n", encoding="utf-8")
    uncited.write_text(
        "theorem uncited_orphan : True := by sorry\n", encoding="utf-8")
    orphan_strat.write_text(
        "theorem s99999 : True := trivial\n", encoding="utf-8")

    _recover_at_startup(conn, tmp_path)

    assert real.exists()             # goal-backed → kept
    assert not uncited.exists()      # orphan, uncited → swept
    assert not orphan_strat.exists()  # orphan strategy file → swept
    assert cited.exists()            # orphan but cited → kept (repair, not delete)


def test_sweep_orphan_only_untracked_and_respects_scope(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """Safety guards (post-incident): the orphan sweep must (1) only
    delete git-UNTRACKED files — a committed proof can lack a current DB
    row (reset/migrated problem) and must NOT be swept — and (2) honor
    `scope` so a scoped run never touches another problem's files."""
    import subprocess
    from Tooling.state.recovery import sweep_orphan_proof_files
    git = lambda *a: subprocess.run(["git", *a], cwd=tmp_path,
                                    capture_output=True)
    if git("init", "-q").returncode != 0:
        pytest.skip("git unavailable")
    git("config", "user.email", "t@t"); git("config", "user.name", "t")

    for name in ("p1", "p2"):
        conn.execute(
            "INSERT INTO problems (name, manifest_path, created_at,"
            " bootstrap_done) VALUES (?, ?, ?, 1)",
            (name, f"Problems/{name}/Manifest.md", db.now()))
    db.insert_goal(conn, problem="p1", slug="real",
                   lean_path="Problems/p1/proofs/L_real.lean",
                   statement="T", origin="backward", status="proved")
    conn.commit()

    p1 = tmp_path / "Problems" / "p1" / "proofs"; p1.mkdir(parents=True)
    p2 = tmp_path / "Problems" / "p2" / "proofs"; p2.mkdir(parents=True)
    (p1 / "L_real.lean").write_text("theorem real : True := trivial\n")
    # tracked + no DB row → committed proof from a reset problem → PROTECT
    (p1 / "L_committed_no_row.lean").write_text(
        "theorem committed_no_row : True := trivial\n")
    git("add", "-A"); git("commit", "-qm", "init")
    # untracked + no DB row → genuine placement orphan → DELETE
    (p1 / "L_untracked_orphan.lean").write_text(
        "theorem untracked_orphan : True := by sorry\n")
    # out-of-scope problem's orphan → must be left alone under scope=p1
    (p2 / "L_p2_orphan.lean").write_text(
        "theorem p2_orphan : True := by sorry\n")

    deleted, kept = sweep_orphan_proof_files(conn, tmp_path, scope="p1")

    assert (p1 / "L_real.lean").exists()             # goal-backed
    assert (p1 / "L_committed_no_row.lean").exists()  # tracked → PROTECTED
    assert not (p1 / "L_untracked_orphan.lean").exists()  # untracked → swept
    assert (p2 / "L_p2_orphan.lean").exists()        # out of scope → untouched
    assert deleted == 1


def test_cmd_run_refuses_no_scope_without_all_problems() -> None:
    """Scope safety gate: `asterism run` with no --scope and no
    --all-problems is refused (rc=2) before any daemon work — a no-scope
    run is workspace-wide and rarely intended."""
    import argparse
    from Tooling.core.cli import cmd_run
    rc = cmd_run(argparse.Namespace(scope=None, all_problems=False,
                                    once=False))
    assert rc == 2


def test_strategist_row_is_stale(conn: sqlite3.Connection) -> None:
    """A queued Strategist whose root already proved is dropped at spawn
    (would only Noop). Guards: open root → keep; proved root → drop;
    non-Strategist kind → never stale; bad/unknown target → not stale."""
    from Tooling.core.dispatcher import _strategist_row_is_stale
    conn.execute(
        "INSERT INTO problems (name, manifest_path, created_at, "
        "bootstrap_done) VALUES (?, ?, ?, 1)",
        ("p", "Problems/p/Manifest.md", db.now()),
    )
    gid = db.insert_goal(
        conn, problem="p", slug="main", lean_path="Problems/p/Root.lean",
        statement="T", origin="root",
    )
    assert _strategist_row_is_stale(conn, str(gid), "Strategist") is False
    db.update_goal_status(conn, gid, "proved")
    assert _strategist_row_is_stale(conn, str(gid), "Strategist") is True
    # A non-Strategist row is never gated by this rule.
    assert _strategist_row_is_stale(conn, str(gid), "Backward") is False
    # Defensive: unknown / non-integer target → not stale (don't wedge).
    assert _strategist_row_is_stale(conn, "999999", "Strategist") is False
    assert _strategist_row_is_stale(conn, "not-an-int", "Strategist") is False


def test_attempt_owner_alive(tmp_path: Path) -> None:
    """#90 liveness probe: live owner_pid → True; dead pid or missing
    manifest → False (orphan, safe to clean)."""
    import os
    import json
    from Tooling.state.recovery import _attempt_owner_alive
    live = tmp_path / "live"
    (live / "sandbox").mkdir(parents=True)
    (live / "sandbox" / "_manifest.json").write_text(
        json.dumps({"owner_pid": os.getpid()}), encoding="utf-8")
    assert _attempt_owner_alive(live) is True
    dead = tmp_path / "dead"
    (dead / "sandbox").mkdir(parents=True)
    (dead / "sandbox" / "_manifest.json").write_text(
        json.dumps({"owner_pid": 2147483646}), encoding="utf-8")  # not running
    assert _attempt_owner_alive(dead) is False
    nomani = tmp_path / "nomani"
    nomani.mkdir()
    assert _attempt_owner_alive(nomani) is False


def test_recover_at_startup_spares_live_attempts(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """#90 — recovery nukes orphan .attempts but spares a live spawn's
    dir (owner_pid alive), so a concurrent non-daemon driver/e2e isn't
    clobbered."""
    import os
    import json
    from Tooling.core.dispatcher import _recover_at_startup
    att = tmp_path / ".attempts"
    live = att / "live-uuid" / "sandbox"
    live.mkdir(parents=True)
    (live / "_manifest.json").write_text(
        json.dumps({"owner_pid": os.getpid()}), encoding="utf-8")
    dead = att / "dead-uuid" / "sandbox"
    dead.mkdir(parents=True)
    (dead / "_manifest.json").write_text(
        json.dumps({"owner_pid": 2147483646}), encoding="utf-8")
    nomani = att / "nomani-uuid"
    nomani.mkdir(parents=True)

    _recover_at_startup(conn, tmp_path)

    assert (att / "live-uuid").exists()       # live spawn spared
    assert not (att / "dead-uuid").exists()   # dead-owner orphan nuked
    assert not (att / "nomani-uuid").exists()  # manifest-less orphan nuked


def test_recover_at_startup_reenqueues_incomplete_inject_forwards(
    conn: sqlite3.Connection,
) -> None:
    """A batched (or solo) Inject(Forward) decision whose Forward never
    produced a terminal outcome must have its queue row restored at
    daemon recovery. Without this, a daemon crash mid-batch leaves
    the strategist_decisions row with outcome=NULL forever —
    inject_batch_done never fires.

    payload.pipeline = 'Forward' → re-enqueue as Forward / Problem.
    """
    from Tooling.core.dispatcher import _recover_at_startup
    import json as _json
    conn.execute(
        "INSERT INTO problems (name, manifest_path, created_at, bootstrap_done)"
        " VALUES ('p', 'Problems/p/Manifest.md', ?, 1)", (db.now(),))
    ts = db.now()
    payload = _json.dumps({"pipeline": "Forward"})
    rids = []
    for outcome, batch_id, brief in [
        ("proved", "batch-A", "done brief"),
        (None,     "batch-A", "pending batched brief"),
        (None,      None,     "pending solo brief"),
    ]:
        cur = conn.execute(
            "INSERT INTO strategist_decisions (problem,"
            " triggered_at_tick, trigger_kind, decision_kind,"
            " brief, payload, batch_id, outcome, created_at, updated_at)"
            " VALUES ('p', 0, 'pending_review', 'Inject',"
            "         ?, ?, ?, ?, ?, ?)",
            (brief, payload, batch_id, outcome, ts, ts))
        rids.append(int(cur.lastrowid))
    conn.commit()

    _recover_at_startup(conn)

    q = list(conn.execute(
        "SELECT kind, target_id, target_kind, decision_id FROM queue"
        " WHERE kind='Forward' ORDER BY decision_id"))
    assert len(q) == 2
    assert {r["decision_id"] for r in q} == {rids[1], rids[2]}
    for r in q:
        assert r["target_id"] == "p"
        assert r["target_kind"] == "Problem"


def test_recover_at_startup_reenqueues_inflight_inject_backward(
    conn: sqlite3.Connection,
) -> None:
    """Inject(Backward) caught mid-flight by a daemon restart MUST be
    re-enqueued as a Backward dispatch on its target goal, not as a
    Forward (the pre-fix hardcoded path that fed Backward briefs into
    Forward workers and produced nonsense lemmas — residue_thm
    2026-05-21 g2494 / s10559).
    """
    from Tooling.core.dispatcher import _recover_at_startup
    import json as _json
    gid = _seed_goal(conn, problem="p")
    ts = db.now()
    payload = _json.dumps({"pipeline": "Backward", "target_goal_id": gid})
    cur = conn.execute(
        "INSERT INTO strategist_decisions (problem,"
        " triggered_at_tick, trigger_kind, decision_kind, target_id,"
        " brief, payload, batch_id, outcome, created_at, updated_at)"
        " VALUES ('p', 0, 'pending_review', 'Inject', ?,"
        "         'try fresh angle', ?, 'batch-bw', NULL, ?, ?)",
        (gid, payload, ts, ts))
    rid = int(cur.lastrowid)
    conn.commit()

    _recover_at_startup(conn)

    q = list(conn.execute(
        "SELECT kind, target_id, target_kind, decision_id FROM queue"))
    assert len(q) == 1
    assert q[0]["kind"] == "Backward"
    assert int(q[0]["target_id"]) == gid
    assert q[0]["target_kind"] == "Goal"
    assert q[0]["decision_id"] == rid


def test_recover_at_startup_reenqueues_inflight_inject_builder(
    conn: sqlite3.Connection,
) -> None:
    """Same per-kind re-enqueue applies to Inject(Builder)."""
    from Tooling.core.dispatcher import _recover_at_startup
    import json as _json
    gid = _seed_goal(conn, problem="p")
    ts = db.now()
    payload = _json.dumps({"pipeline": "Builder", "target_goal_id": gid})
    cur = conn.execute(
        "INSERT INTO strategist_decisions (problem,"
        " triggered_at_tick, trigger_kind, decision_kind, target_id,"
        " brief, payload, batch_id, outcome, created_at, updated_at)"
        " VALUES ('p', 0, 'pending_review', 'Inject', ?,"
        "         'hint', ?, 'batch-build', NULL, ?, ?)",
        (gid, payload, ts, ts))
    rid = int(cur.lastrowid)
    conn.commit()

    _recover_at_startup(conn)

    q = list(conn.execute(
        "SELECT kind, target_id, target_kind, decision_id FROM queue"))
    assert len(q) == 1
    assert q[0]["kind"] == "Builder"
    assert int(q[0]["target_id"]) == gid
    assert q[0]["decision_id"] == rid


def test_recover_at_startup_skips_inject_with_committed_artifact(
    conn: sqlite3.Connection,
) -> None:
    """When the Inject's worker already committed an artifact
    (produced_goal_id for Forward / Builder, produced_strategy_id for
    Backward), the next daemon must NOT re-enqueue: the worker's
    write is on disk + DB, outcome will propagate naturally when the
    artifact reaches terminal, and a second dispatch would spawn a
    duplicate worker with a stale brief.
    """
    from Tooling.core.dispatcher import _recover_at_startup
    import json as _json
    gid = _seed_goal(conn, problem="p")
    # Backward inject that already produced a strategy.
    sid = db.insert_strategy(
        conn, goal_id=gid,
        lean_path="Problems/p/Root.lean",
        scratch_path="Problems/p/proofs/_strategy_s.lean",
        created_by="pid",
    )
    ts = db.now()
    payload = _json.dumps({"pipeline": "Backward", "target_goal_id": gid})
    cur = conn.execute(
        "INSERT INTO strategist_decisions (problem,"
        " triggered_at_tick, trigger_kind, decision_kind, target_id,"
        " brief, payload, batch_id, produced_strategy_id, outcome,"
        " created_at, updated_at)"
        " VALUES ('p', 0, 'pending_review', 'Inject', ?,"
        "         'hint', ?, 'batch-bw', ?, NULL, ?, ?)",
        (gid, payload, sid, ts, ts))
    conn.commit()

    _recover_at_startup(conn)

    q = list(conn.execute("SELECT * FROM queue"))
    assert len(q) == 0  # no re-dispatch; outcome will propagate from
                        # strategy terminal via update_strategy_status

    # Forward inject that already produced a goal.
    fwd_goal = db.insert_goal(
        conn, problem="p", slug="fwd_lem",
        lean_path="Problems/p/proofs/L_fwd_lem.lean",
        statement="T", origin="forward",
    )
    fwd_payload = _json.dumps({"pipeline": "Forward"})
    conn.execute(
        "INSERT INTO strategist_decisions (problem,"
        " triggered_at_tick, trigger_kind, decision_kind,"
        " brief, payload, batch_id, produced_goal_id, outcome,"
        " created_at, updated_at)"
        " VALUES ('p', 0, 'pending_review', 'Inject',"
        "         '## Need\nL', ?, 'batch-fwd', ?, NULL, ?, ?)",
        (fwd_payload, fwd_goal, ts, ts))
    conn.commit()

    _recover_at_startup(conn)

    q = list(conn.execute("SELECT * FROM queue"))
    assert len(q) == 0  # Forward also skipped — goal already on disk


def test_recover_at_startup_flips_open_to_attempting_when_strategy_live(
    conn: sqlite3.Connection,
) -> None:
    """Daemon shutdown race: a Backward worker finishes after the main
    thread already returned (quota fast-fail self-exit via pool.shutdown
    wait=False), writing its strategy + pipeline rows but missing the
    cascade callback that would have flipped goal to 'attempting'.
    Next daemon's bfs_refill would otherwise see goal='open' + dispatch
    a duplicate Backward, producing N parallel live strategies on the
    same goal (residue_thm 2026-05-21 g2458 had s10596 + s10609
    simultaneously). Recovery must reconcile: any 'open' goal with a
    live 'proposed' strategy belongs in 'attempting'.
    """
    from Tooling.core.dispatcher import _recover_at_startup
    # Open goal with a live strategy — the bug shape.
    gid = _seed_goal(conn, problem="p")
    db.update_goal_status(conn, gid, "open")
    sid = db.insert_strategy(
        conn, goal_id=gid,
        lean_path="Problems/p/Root.lean",
        scratch_path="Problems/p/proofs/_strategy_s.lean",
        created_by="pid-orphan-success",
    )

    # A second seed goal that's correctly 'open' with NO live strategy
    # — must NOT be touched.
    gid_clean = db.insert_goal(
        conn, problem="p", slug="clean_open",
        lean_path="Problems/p/proofs/L_clean_open.lean",
        statement="T", origin="backward", depth=1,
    )
    # status defaults to 'open' from insert_goal

    _recover_at_startup(conn)

    assert db.get_goal(conn, gid)["status"] == "attempting"
    assert db.get_goal(conn, gid_clean)["status"] == "open"
    # Strategy itself untouched.
    assert conn.execute(
        "SELECT status FROM strategies WHERE id=?", (sid,),
    ).fetchone()["status"] == "proposed"


def test_recover_at_startup_kills_half_baked_strategies(
    conn: sqlite3.Connection,
) -> None:
    """A 'proposed' strategy with empty scratch_path is from a Backward
    that crashed mid-flight (INSERT done, file/UPDATE not). Recovery must
    mark it 'dead' so subsequent Verify dispatch ignores it."""
    from Tooling.core.dispatcher import _recover_at_startup
    gid = _seed_goal(conn)
    half_baked = db.insert_strategy(conn, goal_id=gid,
                                     lean_path="Problems/p/Root.lean",
                                     created_by="pid-crash",
                                     scratch_path="")
    healthy = db.insert_strategy(conn, goal_id=gid,
                                  lean_path="Problems/p/Root.lean",
                                  created_by="pid-ok",
                                  scratch_path="Problems/p/proofs/_strategy_s2.lean")
    _recover_at_startup(conn)
    assert conn.execute(
        "SELECT status FROM strategies WHERE id = ?", (half_baked,),
    ).fetchone()["status"] == "dead"
    assert conn.execute(
        "SELECT status FROM strategies WHERE id = ?", (healthy,),
    ).fetchone()["status"] == "proposed"


def test_queue_size_helper(conn: sqlite3.Connection) -> None:
    assert db.queue_size(conn) == 0
    db.enqueue(conn, kind="Backward", target_id="1")
    db.enqueue(conn, kind="Builder", target_id="2")
    assert db.queue_size(conn) == 2


def test_run_idle_exits_when_only_shelved_goals(
    conn: sqlite3.Connection,
) -> None:
    """F11: when daemon has no dispatchable work (all goals shelved or
    proved + nothing in flight + queue empty), it exits instead of
    spinning until budget timeout."""
    # We don't run the full dispatcher loop (too heavy); we replicate
    # the idle-exit condition check to confirm the predicate logic.
    _seed_problem_with_root(conn)
    # Goal status='open' initially → not idle
    assert len(db.open_goals(conn)) > 0

    # Shelf the only goal → no dispatchable work
    gid = conn.execute("SELECT id FROM goals WHERE slug='main'").fetchone()["id"]
    db.update_goal_status(conn, gid, "shelved")

    assert len(db.open_goals(conn)) == 0
    assert len(db.strategies_ready_for_verify(conn)) == 0
    assert db.queue_size(conn) == 0
    # Predicate that dispatcher.run() uses to decide idle-exit
    is_idle = (
        len(db.open_goals(conn)) == 0
        and len(db.strategies_ready_for_verify(conn)) == 0
        and db.queue_size(conn) == 0
    )
    assert is_idle


def test_recover_at_startup_clears_orphan_attempts_dirs(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """F2: daemon kill bypasses WorkArea cleanup; child claude subprocesses
    can keep writing to dead parent's dir. Startup must rmtree everything
    in .attempts/ (it's pure transient state; any pre-existing dir is
    stale by definition)."""
    from Tooling.core.dispatcher import _recover_at_startup
    attempts = tmp_path / ".attempts"
    (attempts / "stale-pid-aaa").mkdir(parents=True)
    (attempts / "stale-pid-aaa" / "PROPOSAL.md").write_text("zombie")
    (attempts / "stale-pid-bbb").mkdir(parents=True)
    (attempts / "stale-pid-bbb" / "Context.md").write_text("zombie")

    _recover_at_startup(conn, tmp_path)

    # All orphan dirs cleared; .attempts/ itself may still exist (empty)
    assert not (attempts / "stale-pid-aaa").exists()
    assert not (attempts / "stale-pid-bbb").exists()


def test_recover_at_startup_skips_filesystem_when_workspace_none(
    conn: sqlite3.Connection,
) -> None:
    """DB-only call (test fixtures, etc.) must not crash."""
    from Tooling.core.dispatcher import _recover_at_startup
    _recover_at_startup(conn)  # workspace=None default
    # No assertion needed; reaching here means no exception.


def test_recover_at_startup_restores_backup_when_goal_not_proved(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """F3: a `.lean.backup` left by a killed Builder/Verify means the
    pipeline didn't commit success. Goal is still open in DB. The
    current .lean may hold a half-applied patch; restore the backup."""
    from Tooling.core.dispatcher import _recover_at_startup
    _seed_problem_with_root(conn)  # creates goal at Problems/p/Root.lean

    proofs = tmp_path / "Problems" / "p"
    proofs.mkdir(parents=True)
    (proofs / "Root.lean").write_text("PATCH-IN-PROGRESS")
    (proofs / "Root.lean.backup").write_text("ORIGINAL-SORRY")

    _recover_at_startup(conn, tmp_path)

    assert (proofs / "Root.lean").read_text() == "ORIGINAL-SORRY"
    assert not (proofs / "Root.lean.backup").exists()


def test_recover_at_startup_discards_backup_when_goal_proved(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """F3: if the goal is 'proved' in DB, the pipeline DID commit success
    — the daemon died in the race window between lake-build success and
    backup.unlink. Current .lean is the validated proof; restoring the
    backup would destroy it. Just discard the backup."""
    from Tooling.core.dispatcher import _recover_at_startup
    gid = _seed_problem_with_root(conn)
    db.update_goal_status(conn, gid, "proved")

    proofs = tmp_path / "Problems" / "p"
    proofs.mkdir(parents=True)
    (proofs / "Root.lean").write_text("VALIDATED-PROOF")
    (proofs / "Root.lean.backup").write_text("ORIGINAL-SORRY")

    _recover_at_startup(conn, tmp_path)

    assert (proofs / "Root.lean").read_text() == "VALIDATED-PROOF"
    assert not (proofs / "Root.lean.backup").exists()


def test_recover_at_startup_handles_verify_backup(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """F3: same logic for `.lean.verify_backup` from killed Verify."""
    from Tooling.core.dispatcher import _recover_at_startup
    _seed_problem_with_root(conn)

    proofs = tmp_path / "Problems" / "p"
    proofs.mkdir(parents=True)
    (proofs / "Root.lean").write_text("ALIAS-IN-PROGRESS")
    (proofs / "Root.lean.verify_backup").write_text("ORIGINAL")

    _recover_at_startup(conn, tmp_path)

    assert (proofs / "Root.lean").read_text() == "ORIGINAL"
    assert not (proofs / "Root.lean.verify_backup").exists()


def test_recover_at_startup_discards_backup_when_goal_missing(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """F3 / SG 2026-05-18 regression: if no goal row references the
    .lean path, the operator wiped state (cli reset / DB drop) but the
    backup variant survived because reset's glob didn't cover it.
    Restoring would resurrect a goal-less orphan that the next
    Strategist could `have`-into a downstream proof — soft-corrupting
    the tree with a sorry the framework never re-validates. Discard."""
    from Tooling.core.dispatcher import _recover_at_startup
    # NO goal row inserted — simulates post-reset state where the goal
    # was wiped but a sid-keyed backup survived (the original bug).
    proofs = tmp_path / "Problems" / "p"
    proofs.mkdir(parents=True)
    (proofs / "L_orphan.lean.verify_backup_s9983").write_text(
        "theorem orphan : True := by sorry")

    _recover_at_startup(conn, tmp_path)

    # Backup discarded, NOT restored — no goal-less L_orphan.lean
    # appears on disk.
    assert not (proofs / "L_orphan.lean.verify_backup_s9983").exists()
    assert not (proofs / "L_orphan.lean").exists()


def test_recover_at_startup_removes_tmp_files(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """F3: .lean.tmp from killed Verify (between write and os.replace)
    holds partial content. Never safe to use; always unlink."""
    from Tooling.core.dispatcher import _recover_at_startup
    proofs = tmp_path / "Problems" / "p"
    proofs.mkdir(parents=True)
    (proofs / "Root.lean").write_text("OK")
    (proofs / "Root.lean.tmp").write_text("PARTIAL-WRITE")

    _recover_at_startup(conn, tmp_path)

    assert (proofs / "Root.lean").read_text() == "OK"
    assert not (proofs / "Root.lean.tmp").exists()


def _seed_problem_with_root(conn: sqlite3.Connection) -> int:
    """Helper: insert a problem + open root goal at Problems/p/Root.lean."""
    conn.execute(
        "INSERT INTO problems (name, manifest_path, created_at, bootstrap_done) VALUES (?, ?, ?, 1)",
        ("p", "Problems/p/Manifest.md", db.now()),
    )
    return db.insert_goal(
        conn, problem="p", slug="main",
        lean_path="Problems/p/Root.lean",
        statement="T", origin="root",
    )


def test_recover_at_startup_reopens_stuck_attempting_goals(
    conn: sqlite3.Connection,
) -> None:
    """Goal in 'attempting' with no surviving 'proposed' strategy is stuck
    — bfs_refill won't dispatch it. Recovery must reset to 'open'.
    Goals with at least one 'proposed' strategy are left alone."""
    from Tooling.core.dispatcher import _recover_at_startup
    # Stuck root: 'attempting' with only a 'dead' strategy
    stuck = _seed_goal(conn)
    db.update_goal_status(conn, stuck, "attempting")
    dead_strat = db.insert_strategy(conn, goal_id=stuck,
                                     lean_path="Problems/p/Root.lean",
                                     created_by="pid-old")
    db.update_strategy_status(conn, dead_strat, "dead")

    # Alive root: 'attempting' with a still-'proposed' strategy
    alive = db.insert_goal(
        conn, problem="p", slug="alive_main",
        lean_path="Problems/p/Alive.lean", statement="T",
        origin="root",
    )
    db.update_goal_status(conn, alive, "attempting")
    db.insert_strategy(conn, goal_id=alive,
                       lean_path="Problems/p/Alive.lean",
                       created_by="pid-live",
                       scratch_path="Problems/p/proofs/_strategy_alive.lean")

    _recover_at_startup(conn)

    assert db.get_goal(conn, stuck)["status"] == "open"
    assert db.get_goal(conn, alive)["status"] == "attempting"


def test_open_goals_recursive_orphan_filter(conn: sqlite3.Connection) -> None:
    """E8 fix: orphan filter must walk the full ancestor chain. A depth-2
    sub-goal whose immediate parent strategy is 'proposed' but whose
    grandparent strategy is 'superseded' must still be filtered out.

    Bug scenario from cantor smoke restart against compactness leftover:
    s4 (root strategy, OR loser) was 'superseded'; goal 41 (s4's sub-goal)
    was 'open' and properly orphan-filtered; but goal 41's own strategy
    s11 was still 'proposed', so goal 51 (s11's sub-sub-goal) was
    incorrectly considered eligible and dispatched."""
    root = _seed_goal(conn)
    # Root has a 'superseded' strategy (e.g. OR loser)
    s_root = db.insert_strategy(conn, goal_id=root,
                                 lean_path="Problems/p/Root.lean",
                                 created_by="pid-root")
    db.update_strategy_status(conn, s_root, "superseded")

    sub = db.insert_goal(
        conn, problem="p", slug="depth1_orphan",
        lean_path="Problems/p/proofs/L_depth1_orphan.lean",
        statement="T", origin="backward", depth=1,
    )
    db.link_subgoal(conn, strategy_id=s_root, subgoal_id=sub, position=0)

    # Depth-2: sub's strategy is still 'proposed' (just hadn't been
    # cleaned up in the cascade). Without recursive filter, the
    # sub-sub-goal looks eligible.
    s_sub = db.insert_strategy(conn, goal_id=sub,
                                lean_path=f"Problems/p/proofs/L_depth1_orphan.lean",
                                created_by="pid-sub")
    sub_sub = db.insert_goal(
        conn, problem="p", slug="depth2_orphan",
        lean_path="Problems/p/proofs/L_depth2_orphan.lean",
        statement="T", origin="backward", depth=2,
    )
    db.link_subgoal(conn, strategy_id=s_sub, subgoal_id=sub_sub, position=0)

    ids = [g["id"] for g in db.open_goals(conn)]
    assert sub not in ids        # immediate orphan, prior fix
    assert sub_sub not in ids    # recursive orphan, E8 fix
    assert root in ids           # root always eligible


def test_queue_count_helper(conn: sqlite3.Connection) -> None:
    db.enqueue(conn, kind="Backward", target_id="42")
    db.enqueue(conn, kind="Backward", target_id="42")
    db.enqueue(conn, kind="Builder", target_id="42")
    assert db.queue_count(conn, target_id="42", kind="Backward") == 2
    assert db.queue_count(conn, target_id="42", kind="Builder") == 1
    assert db.queue_count(conn, target_id="99", kind="Backward") == 0


def test_bfs_refill_backward_capped_at_one(conn: sqlite3.Connection) -> None:
    """F37 — for an open goal whose next worker is Backward, bfs_refill
    enqueues exactly one entry (passive trigger; sequential expansion)."""
    from Tooling.core.dispatcher import bfs_refill, BUILDER_THRESHOLD
    gid = _seed_goal(conn)
    # Bump attempts past BUILDER_THRESHOLD so next_worker_kind escalates
    # to Backward (the entry_kind=Builder default would otherwise route
    # to Builder; threshold is the safety-net escalation).
    for _ in range(BUILDER_THRESHOLD):
        db.increment_goal_attempts(conn, gid)
    bfs_refill(conn, running=set())
    assert db.queue_count(conn, target_id=str(gid), kind="Backward") == 1


def test_bfs_refill_builder_capped_at_one(conn: sqlite3.Connection) -> None:
    """F37 — Builder is also single-attempt-per-goal."""
    from Tooling.core.dispatcher import bfs_refill
    gid = _seed_goal(conn)  # default entry_kind=Builder, attempts=0 → Builder
    bfs_refill(conn, running=set())
    assert db.queue_count(conn, target_id=str(gid), kind="Builder") == 1


def test_bfs_refill_no_duplicate_when_already_running(
    conn: sqlite3.Connection,
) -> None:
    """F37 — bfs_refill must not enqueue if a pipeline of the same
    (target_id, kind) is already in flight (in `running` set)."""
    from Tooling.core.dispatcher import bfs_refill
    gid = _seed_goal(conn)
    bfs_refill(conn, running={(str(gid), "Backward")})
    assert db.queue_count(conn, target_id=str(gid), kind="Backward") == 0


def test_bfs_refill_skips_goal_with_any_kind_in_flight(
    conn: sqlite3.Connection,
) -> None:
    """2026-05-28: bfs_refill defers when ANY pipeline (any kind) is
    already in flight on the goal. Prevents racing Strategist Inject —
    Inject(Builder) enqueues a Builder; bfs_refill must not enqueue a
    parallel Backward of its own under threshold escalation.
    (LU lu_step_assembly 2026-05-28 regression.)"""
    from Tooling.core.dispatcher import bfs_refill
    gid = _seed_goal(conn)
    db.update_goal_entry_kind(conn, gid, "Backward")
    # Simulate Strategist Inject(Builder) sitting in queue.
    db.enqueue(conn, kind="Builder", target_id=str(gid), priority=10,
               decision_id=None)
    bfs_refill(conn, running=set())
    # No additional Backward should be enqueued.
    assert db.queue_count(conn, target_id=str(gid), kind="Backward") == 0
    assert db.queue_count(conn, target_id=str(gid), kind="Builder") == 1


def test_bfs_refill_skips_goal_with_any_kind_running(
    conn: sqlite3.Connection,
) -> None:
    """Symmetric to the queued-Builder case: a Builder already running
    (in `running` set) blocks bfs_refill from enqueueing a Backward of
    its own."""
    from Tooling.core.dispatcher import bfs_refill
    gid = _seed_goal(conn)
    db.update_goal_entry_kind(conn, gid, "Backward")
    bfs_refill(conn, running={(str(gid), "Builder", None)})
    assert db.queue_count(conn, target_id=str(gid), kind="Backward") == 0


def test_bfs_refill_scope_filters_by_problem(
    conn: sqlite3.Connection,
) -> None:
    """`scope` (SQL LIKE) restricts dispatch to matching problems. Used
    by `python -m Tooling.cli run --scope <pattern>` so a benchmark
    daemon doesn't dispatch unrelated research problems sharing the
    workspace."""
    from Tooling.core.dispatcher import bfs_refill
    gid_research = _seed_goal(conn, problem="sylvester_gallai")
    # Second problem via direct insert (avoid _seed_goal's duplicate-problem
    # behavior).
    conn.execute(
        "INSERT INTO problems (name, manifest_path, created_at, bootstrap_done) "
        "VALUES (?, ?, ?, 1)",
        ("minif2f_x", "Problems/minif2f_x/Manifest.md", db.now()),
    )
    gid_bench = db.insert_goal(
        conn, problem="minif2f_x", slug="main",
        lean_path="Problems/minif2f_x/Root.lean",
        statement="T", origin="root",
    )

    # Scope to minif2f only → only benchmark goal queues
    bfs_refill(conn, running=set(), scope="minif2f_%")
    assert db.queue_count(conn, target_id=str(gid_bench), kind="Builder") == 1
    assert db.queue_count(conn,
                          target_id=str(gid_research), kind="Builder") == 0


def test_bfs_refill_no_scope_dispatches_all(
    conn: sqlite3.Connection,
) -> None:
    """Without scope arg, dispatch is workspace-wide (back-compat)."""
    from Tooling.core.dispatcher import bfs_refill
    gid1 = _seed_goal(conn, problem="sg")
    conn.execute(
        "INSERT INTO problems (name, manifest_path, created_at, bootstrap_done) "
        "VALUES (?, ?, ?, 1)",
        ("pn", "Problems/pn/Manifest.md", db.now()),
    )
    gid2 = db.insert_goal(
        conn, problem="pn", slug="main",
        lean_path="Problems/pn/Root.lean",
        statement="T", origin="root",
    )
    bfs_refill(conn, running=set())  # no scope
    assert db.queue_count(conn, target_id=str(gid1), kind="Builder") == 1
    assert db.queue_count(conn, target_id=str(gid2), kind="Builder") == 1


def test_bfs_refill_kind_cooldown_blocks_enqueue(
    conn: sqlite3.Connection,
) -> None:
    """#103 — when a kind is in quota cooldown, bfs_refill skips every
    target of that kind even if no per-target cooldown is set."""
    import time
    from Tooling.core.dispatcher import bfs_refill
    _seed_goal(conn, problem="sg")  # default attempts=0 → Builder
    qcd = {"Builder": time.time() + 60.0}
    bfs_refill(conn, running=set(), quota_cooldown_kind=qcd)
    assert db.queue_size(conn) == 0


def test_bfs_refill_kind_cooldown_only_affects_matching_kind(
    conn: sqlite3.Connection,
) -> None:
    """#103 — cooling Backward does not block Builder targets, and
    vice versa. Per-kind isolation."""
    import time
    from Tooling.core.dispatcher import bfs_refill, BUILDER_THRESHOLD
    gid_b = _seed_goal(conn, problem="sg")  # entry=Builder, attempts=0
    conn.execute(
        "INSERT INTO problems (name, manifest_path, created_at, bootstrap_done) "
        "VALUES (?, ?, ?, 1)",
        ("pn", "Problems/pn/Manifest.md", db.now()),
    )
    gid_bw = db.insert_goal(
        conn, problem="pn", slug="main",
        lean_path="Problems/pn/Root.lean",
        statement="T", origin="root",
    )
    for _ in range(BUILDER_THRESHOLD):
        db.increment_goal_attempts(conn, gid_bw)  # escalate to Backward
    bfs_refill(conn, running=set(),
               quota_cooldown_kind={"Backward": time.time() + 60.0})
    assert db.queue_count(conn, target_id=str(gid_b), kind="Builder") == 1
    assert db.queue_count(conn, target_id=str(gid_bw), kind="Backward") == 0


def test_bfs_refill_expired_kind_cooldown_no_block(
    conn: sqlite3.Connection,
) -> None:
    """#103 — past-epoch entry in quota_cooldown_kind doesn't gate."""
    import time
    from Tooling.core.dispatcher import bfs_refill
    gid = _seed_goal(conn, problem="sg")
    bfs_refill(conn, running=set(),
               quota_cooldown_kind={"Builder": time.time() - 60.0})
    assert db.queue_count(conn, target_id=str(gid), kind="Builder") == 1


def test_flush_queue_kind_drops_only_matching(
    conn: sqlite3.Connection,
) -> None:
    """#103 — `db.flush_queue_kind` clears every queued entry of `kind`
    and leaves other kinds untouched. Used when quota cooldown engages
    to drop the pre-cooldown backlog."""
    _seed_goal(conn, problem="sg")  # → Builder enqueue via bfs_refill
    conn.execute(
        "INSERT INTO problems (name, manifest_path, created_at, bootstrap_done) "
        "VALUES (?, ?, ?, 1)",
        ("pn", "Problems/pn/Manifest.md", db.now()),
    )
    gid_bw = db.insert_goal(
        conn, problem="pn", slug="main",
        lean_path="Problems/pn/Root.lean",
        statement="T", origin="root",
    )
    from Tooling.core.dispatcher import bfs_refill, BUILDER_THRESHOLD
    for _ in range(BUILDER_THRESHOLD):
        db.increment_goal_attempts(conn, gid_bw)
    bfs_refill(conn, running=set())  # enqueues 1 Builder + 1 Backward
    assert db.queue_size(conn) == 2

    n = db.flush_queue_kind(conn, kind="Backward")
    assert n == 1
    assert db.queue_size(conn) == 1
    rest = db.pop_queue(conn)
    assert rest is not None and rest["kind"] == "Builder"


def test_open_goals_excludes_frozen_root(
    conn: sqlite3.Connection,
) -> None:
    """Phase 5: roots are inserted with status='frozen' until Strategist
    issues `Reopen(root)` (frozen→open). `db.open_goals` filters
    status='open' so frozen roots are invisible to BFS. Replaces the
    legacy bootstrap_done-based gate while preserving the same first-launch
    race protection.
    """
    conn.execute(
        "INSERT INTO problems (name, manifest_path, created_at) "
        "VALUES (?, ?, ?)",
        ("p", "Problems/p/Manifest.md", db.now()),
    )
    root = db.insert_goal(
        conn, problem="p", slug="main",
        lean_path="Problems/p/Root.lean",
        statement="T", origin="root", status="frozen",
    )
    conn.commit()

    # Frozen root: open_goals returns empty.
    assert db.open_goals(conn) == []

    # After Strategist Reopen flips it to 'open', root surfaces.
    db.update_goal_status(conn, root, "open")
    after = db.open_goals(conn)
    assert len(after) == 1
    assert after[0]["id"] == root


def test_open_goals_scope_filter(conn: sqlite3.Connection) -> None:
    """Underlying `db.open_goals(scope=...)` SQL filter. Direct unit test
    so the scope plumbing is covered even if bfs_refill restructures."""
    _seed_goal(conn, problem="sg")
    conn.execute(
        "INSERT INTO problems (name, manifest_path, created_at, bootstrap_done) "
        "VALUES (?, ?, ?, 1)",
        ("minif2f_a", "Problems/minif2f_a/Manifest.md", db.now()),
    )
    db.insert_goal(
        conn, problem="minif2f_a", slug="main",
        lean_path="Problems/minif2f_a/Root.lean",
        statement="T", origin="root",
    )

    all_open = db.open_goals(conn)
    assert len(all_open) == 2

    minif2f_only = db.open_goals(conn, scope="minif2f_%")
    assert len(minif2f_only) == 1
    assert minif2f_only[0]["problem"] == "minif2f_a"


def _seed_ready_strategy(conn: sqlite3.Connection, *, goal_id: int,
                         slug: str = "s_x", lean_path: str | None = None) -> int:
    """Insert a strategy on `goal_id` with one already-proved sub-goal,
    so it appears in `strategies_ready_for_verify`."""
    sid = db.insert_strategy(
        conn, goal_id=goal_id,
        lean_path=lean_path or "Problems/p/Root.lean",
        created_by=f"pid-{slug}",
    )
    sub_gid = db.insert_goal(
        conn, problem="p", slug=f"{slug}_sub",
        lean_path=f"Problems/p/proofs/L_{slug}_sub.lean",
        statement="T", origin="backward", depth=1,
    )
    db.update_goal_status(conn, sub_gid, "proved")
    db.link_subgoal(conn, strategy_id=sid, subgoal_id=sub_gid, position=0)
    return sid


# F56 — bfs_refill no longer enqueues Verify pipelines (verify is
# inline housekeeping). Per-goal serialization is no longer needed
# either: housekeeping runs serially within the dispatcher tick, so
# two sibling strategies on the same parent are handled one at a
# time naturally.


def test_strategies_ready_for_verify_excludes_proved_goal(
    conn: sqlite3.Connection,
) -> None:
    """W6 fix: a strategy whose own goal is already proved (by sibling
    OR strategy) must NOT be returned as ready, even if its sub-goals
    are all proved. Prevents the Verify-thrashing loop seen in
    compactness smoke."""
    gid = _seed_goal(conn)
    sid = db.insert_strategy(
        conn, goal_id=gid, lean_path="Problems/p/Root.lean",
        created_by="pid",
        scratch_path="Problems/p/proofs/_strategy_s1.lean",
    )
    sub_gid = db.insert_goal(
        conn, problem="p", slug="proved_sub",
        lean_path="Problems/p/proofs/L_proved_sub.lean",
        statement="T", origin="backward", depth=1,
    )
    db.update_goal_status(conn, sub_gid, "proved")
    db.link_subgoal(conn, strategy_id=sid, subgoal_id=sub_gid, position=0)

    # While goal is open: ready
    assert any(s["id"] == sid for s in db.strategies_ready_for_verify(conn))

    # Once goal is proved (by sibling): NOT ready
    db.update_goal_status(conn, gid, "proved")
    assert not any(s["id"] == sid for s in db.strategies_ready_for_verify(conn))


def test_strategies_ready_for_verify_includes_zero_subgoal_leaf_bypass(
    conn: sqlite3.Connection,
) -> None:
    """Phase 6.5 — a Backward leaf-bypass strategy commits with 0 sub-goals
    (agent wrote a complete proof in patch.lean, no decomposition). Such
    a strategy must qualify for Verify on the next housekeeping tick:
    the NOT EXISTS-unproved-subs clause is vacuously true with 0 rows.
    `scratch_path != ''` gates pre-commit / dead strategies out so an
    abandoned-mid-flight row doesn't accidentally qualify."""
    gid = _seed_goal(conn)
    # Leaf-bypass: strategy committed with scratch_path set, 0 sub-goals.
    sid = db.insert_strategy(
        conn, goal_id=gid, lean_path="Problems/p/Root.lean",
        created_by="pid-leaf",
        scratch_path="Problems/p/proofs/_strategy_s1.lean",
    )
    assert any(s["id"] == sid for s in db.strategies_ready_for_verify(conn))

    # Pre-commit (scratch_path empty) state must NOT qualify, otherwise
    # mid-flight strategies would race ahead of their own commit.
    sid2 = db.insert_strategy(
        conn, goal_id=gid, lean_path="Problems/p/Root.lean",
        created_by="pid-incomplete",
    )
    assert not any(s["id"] == sid2 for s in db.strategies_ready_for_verify(conn))


# ---------------------------------------------------------------------
# integrity_verified marker — gate fires once per root, not every tick.
#
# Regression: dispatcher used to iterate `manifests` every loop and
# call `verify.root_integrity_gate` for every proved root, paying one
# gateway-driven axiom_probe per problem per tick. A workspace with
# 244 proved miniF2F benchmarks stalled new dispatch for ~115min on
# every restart. The fix moves the gate trigger to a DB-driven query
# (`db.unverified_proved_roots`) backed by a `goals.integrity_verified`
# column that gets set once on pass and auto-cleared whenever the root
# leaves 'proved' (cascade rollback path).
# ---------------------------------------------------------------------

def test_root_proved_with_scope_filter_isolates_scoped_problem(
    conn: sqlite3.Connection,
) -> None:
    """SG 2026-05-19 regression: `--scope sylvester_gallai` daemon
    exited with `roots_proved=False` + rc=1 because the unfiltered
    `db.root_proved(conn)` saw unrelated miniF2F roots in the same
    workspace and reported global state, not scoped. Without the
    scope filter, the scoped daemon's "success" can never be reached
    via this exit path."""
    # Seed: SG root proved, an unrelated miniF2F root still open.
    sg_root = _seed_goal(conn, problem="sylvester_gallai")
    db.update_goal_status(conn, sg_root, "proved")
    conn.execute(
        "INSERT INTO problems (name, manifest_path, created_at, bootstrap_done)"
        " VALUES (?, ?, ?, 1)",
        ("Minif2f.imo_1965_p1", "Problems/Minif2f/imo_1965_p1/Manifest.md",
         db.now()),
    )
    db.insert_goal(
        conn, problem="Minif2f.imo_1965_p1", slug="main",
        lean_path="Problems/Minif2f/imo_1965_p1/Root.lean",
        statement="T", origin="root",
    )
    conn.commit()

    # Unfiltered: miniF2F root is open → False.
    assert db.root_proved(conn) is False
    # Scoped to SG: only SG root in scope, proved → True.
    assert db.root_proved(conn, scope="sylvester_gallai") is True
    # LIKE pattern that matches both: still False (miniF2F open).
    assert db.root_proved(conn, scope="%") is False
    # `problem=` exact match still works (back-compat).
    assert db.root_proved(conn, problem="sylvester_gallai") is True
    assert db.root_proved(conn, problem="Minif2f.imo_1965_p1") is False


def test_unverified_proved_roots_empty_until_root_proved(
    conn: sqlite3.Connection,
) -> None:
    gid = _seed_goal(conn)
    assert db.unverified_proved_roots(conn) == []
    db.update_goal_status(conn, gid, "proved")
    assert db.unverified_proved_roots(conn) == ["p"]


def test_unverified_proved_roots_excludes_verified(
    conn: sqlite3.Connection,
) -> None:
    """Once `set_integrity_verified` marks the root, the dispatcher gate
    query must drop it. Without this the gate re-fires every tick."""
    gid = _seed_goal(conn)
    db.update_goal_status(conn, gid, "proved")
    db.set_integrity_verified(conn, gid)
    assert db.unverified_proved_roots(conn) == []


def test_update_goal_status_off_proved_clears_integrity_verified(
    conn: sqlite3.Connection,
) -> None:
    """Cascade rollback flips the root off 'proved' via
    `update_goal_status`; that path must clear `integrity_verified` so
    the next successful re-proof re-enters the gate. Tested at the
    helper level so any caller flipping status (rollback, manual reset,
    future code paths) inherits the invariant for free."""
    gid = _seed_goal(conn)
    db.update_goal_status(conn, gid, "proved")
    db.set_integrity_verified(conn, gid)
    db.update_goal_status(conn, gid, "attempting")  # rollback path
    assert db.unverified_proved_roots(conn) == []  # not proved → not listed
    db.update_goal_status(conn, gid, "proved")
    assert db.unverified_proved_roots(conn) == ["p"]  # re-entered


def test_unverified_proved_roots_ignores_sub_goal_integrity(
    conn: sqlite3.Connection,
) -> None:
    """The marker is meaningful only for origin='root'. A sub-goal that
    happens to be proved must never surface in the gate query (it has
    no axiom_probe to run)."""
    _seed_goal(conn)  # root, status='open'
    sub = db.insert_goal(
        conn, problem="p", slug="sub", lean_path="Problems/p/proofs/sub.lean",
        statement="T", origin="backward",
    )
    db.update_goal_status(conn, sub, "proved")
    assert db.unverified_proved_roots(conn) == []


def test_init_schema_backfills_existing_proved_roots(tmp_path: Path) -> None:
    """Migration-day invariant: on first init_schema call against a DB
    that pre-dated `integrity_verified`, every already-proved root
    flips to verified=1. Without this the first dispatcher tick on a
    benchmark-loaded workspace would re-pay ~110min of axiom_probe.

    Simulates the pre-migration state by stripping the column from a
    fresh DB, inserting a proved root + an open root + a proved
    sub-goal, then re-running init_schema and asserting only the
    proved root picked up the backfill."""
    import sqlite3 as _sql
    path = tmp_path / "legacy.db"
    c = _sql.connect(str(path))
    c.row_factory = _sql.Row
    c.execute("PRAGMA foreign_keys = ON")
    db.init_schema(c)
    # Strip column to simulate a DB built against the prior schema.
    c.execute("ALTER TABLE goals DROP COLUMN integrity_verified")
    # Seed: one proved root (backfill target), one open root (no-op),
    # one proved sub-goal (no-op — column meaningful only for roots).
    c.execute(
        "INSERT INTO problems (name, manifest_path, created_at, bootstrap_done)"
        " VALUES (?, ?, ?, 1)", ("p", "Problems/p/Manifest.md", db.now()))
    proved_root = db.insert_goal(
        c, problem="p", slug="main", lean_path="Problems/p/Root.lean",
        statement="T", origin="root",
    )
    db.update_goal_status(c, proved_root, "proved")
    open_root = db.insert_goal(
        c, problem="p", slug="open_main",
        lean_path="Problems/p/RootB.lean",
        statement="U", origin="root",
    )
    proved_sub = db.insert_goal(
        c, problem="p", slug="sub",
        lean_path="Problems/p/proofs/sub.lean",
        statement="V", origin="backward",
    )
    db.update_goal_status(c, proved_sub, "proved")
    # Re-run migration: backfill should trigger.
    db.init_schema(c)
    row = lambda gid: c.execute(
        "SELECT integrity_verified FROM goals WHERE id = ?", (gid,)
    ).fetchone()["integrity_verified"]
    assert row(proved_root) == 1, "proved root must be backfilled"
    assert row(open_root) == 0, "non-proved root must stay 0"
    assert row(proved_sub) == 0, "proved sub-goal must stay 0 (column is root-only)"
    c.close()


def test_set_integrity_verified_persists_only_when_marker_present(
    conn: sqlite3.Connection,
) -> None:
    """Migration safety: fresh DB built from current SCHEMA must have
    the column, and the helper must succeed without raising. Also
    guards against accidentally dropping the column in a future
    refactor (test would fail at the UPDATE)."""
    gid = _seed_goal(conn)
    db.update_goal_status(conn, gid, "proved")
    db.set_integrity_verified(conn, gid)
    row = conn.execute(
        "SELECT integrity_verified FROM goals WHERE id = ?", (gid,)
    ).fetchone()
    assert row["integrity_verified"] == 1


# F56 — `cascade_one(kind="Verify")` no longer exists. The W6
# "stale proposed strategy on a proved goal" finalization is handled
# by `verify.verify_strategy` returning "superseded"; see
# `tests/test_verify.py`.


# ---------------------------------------------------------------------
# _problem_of_target — resolve problem from a dispatch target
# ---------------------------------------------------------------------

def test_problem_of_target_resolves_goal_to_problem(
    conn: sqlite3.Connection,
) -> None:
    gid = _seed_goal(conn, problem="alpha")
    assert _dispatcher._problem_of_target(
        conn, str(gid), "Goal") == "alpha"


def test_problem_of_target_forward_target_is_problem_name(
    conn: sqlite3.Connection,
) -> None:
    """Forward dispatches use target_kind='Problem'; the target_id IS
    the problem name (string), no goal lookup needed."""
    assert _dispatcher._problem_of_target(
        conn, "some_problem_name", "Problem") == "some_problem_name"


def test_problem_of_target_unknown_goal_returns_none(
    conn: sqlite3.Connection,
) -> None:
    """Defensive: stale queue row pointing at a nonexistent goal must
    not crash the pop loop. _problem_of_target returns None; caller
    skips dispatch."""
    assert _dispatcher._problem_of_target(
        conn, "9999999", "Goal") is None


def test_problem_of_target_non_numeric_goal_returns_none(
    conn: sqlite3.Connection,
) -> None:
    """Defensive: malformed target_id (not int-castable) on a Goal
    dispatch returns None instead of raising ValueError."""
    assert _dispatcher._problem_of_target(
        conn, "not-a-number", "Goal") is None


# ---------------------------------------------------------------------
# bfs_refill — verified_problems quarantine
# ---------------------------------------------------------------------

def test_bfs_refill_skips_quarantined_problem(
    conn: sqlite3.Connection,
) -> None:
    """A problem flagged False in `verified_problems` must NOT have its
    goals enqueued. Prevents the daemon from burning worker spawns on
    a problem whose Defs.lean / Root.lean failed lake build."""
    from Tooling.core.dispatcher import bfs_refill
    gid = _seed_goal(conn, problem="bad_problem")
    bfs_refill(conn, set(), verified_problems={"bad_problem": False})
    rows = conn.execute(
        "SELECT COUNT(*) c FROM queue WHERE target_id = ?",
        (str(gid),),
    ).fetchone()
    assert rows["c"] == 0


def test_bfs_refill_enqueues_unverified_problem(
    conn: sqlite3.Connection,
) -> None:
    """An UNVERIFIED problem (not yet in verified_problems) is still
    enqueued — verification is lazy and happens at the pop site, not
    here. Without this we'd never dispatch the first goal of a new
    problem (chicken/egg)."""
    from Tooling.core.dispatcher import bfs_refill
    gid = _seed_goal(conn, problem="fresh_problem")
    bfs_refill(conn, set(), verified_problems={})  # not yet verified
    rows = conn.execute(
        "SELECT COUNT(*) c FROM queue WHERE target_id = ?",
        (str(gid),),
    ).fetchone()
    assert rows["c"] == 1


def test_bfs_refill_enqueues_passed_problem(
    conn: sqlite3.Connection,
) -> None:
    """A problem flagged True passes through normally."""
    from Tooling.core.dispatcher import bfs_refill
    gid = _seed_goal(conn, problem="good_problem")
    bfs_refill(conn, set(), verified_problems={"good_problem": True})
    rows = conn.execute(
        "SELECT COUNT(*) c FROM queue WHERE target_id = ?",
        (str(gid),),
    ).fetchone()
    assert rows["c"] == 1


# ---------------------------------------------------------------------
# _acquire_singleton_lock — PID-reuse-proof daemon lock
# ---------------------------------------------------------------------

def _write_lock(workspace: Path, text: str) -> Path:
    d = workspace / ".asterism"
    d.mkdir(parents=True, exist_ok=True)
    p = d / "daemon.pid"
    p.write_text(text, encoding="utf-8")
    return p


def test_singleton_lock_acquires_when_no_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No lock → acquire, writing `pid\nstart_time`."""
    import os
    monkeypatch.setattr(_dispatcher, "_proc_start_time", lambda pid: 1000.0)
    p = _dispatcher._acquire_singleton_lock(tmp_path)
    assert p == tmp_path / ".asterism" / "daemon.pid"
    lines = p.read_text(encoding="utf-8").split("\n")
    assert lines[0] == str(os.getpid())
    assert lines[1] == "1000.0"


def test_singleton_lock_blocks_same_live_instance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A live PID whose start-time MATCHES the recorded one is the same
    daemon instance → refuse (return None)."""
    _write_lock(tmp_path, "99999\n5000.0")
    monkeypatch.setattr(_dispatcher, "_pid_alive", lambda pid: pid == 99999)
    monkeypatch.setattr(_dispatcher, "_proc_start_time",
                        lambda pid: 5000.0 if pid == 99999 else 1.0)
    assert _dispatcher._acquire_singleton_lock(tmp_path) is None


def test_singleton_lock_stale_on_pid_reuse(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """THE BUG FIX: the PID is alive but it's a DIFFERENT process (the OS
    reused a crashed daemon's PID) — its start-time differs, so the lock is
    stale and we acquire. Pre-fix this blocked every restart (2026-06-15: a
    crashed daemon's PID was reused by the editor)."""
    import os
    _write_lock(tmp_path, "99999\n5000.0")
    monkeypatch.setattr(_dispatcher, "_pid_alive", lambda pid: True)
    monkeypatch.setattr(_dispatcher, "_proc_start_time",
                        lambda pid: 9000.0)   # different instance
    p = _dispatcher._acquire_singleton_lock(tmp_path)
    assert p is not None
    assert p.read_text(encoding="utf-8").split("\n")[0] == str(os.getpid())


def test_singleton_lock_stale_on_dead_pid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A dead PID → stale → acquire."""
    _write_lock(tmp_path, "99999\n5000.0")
    monkeypatch.setattr(_dispatcher, "_pid_alive", lambda pid: False)
    monkeypatch.setattr(_dispatcher, "_proc_start_time", lambda pid: 1.0)
    assert _dispatcher._acquire_singleton_lock(tmp_path) is not None


def test_singleton_lock_legacy_blocks_live_daemon(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Legacy pid-only lock (no start-time): fall back to the cmdline
    signature. A live process that IS a daemon → refuse."""
    _write_lock(tmp_path, "99999")
    monkeypatch.setattr(_dispatcher, "_pid_alive", lambda pid: True)
    monkeypatch.setattr(_dispatcher, "_cmdline_is_daemon", lambda pid: True)
    assert _dispatcher._acquire_singleton_lock(tmp_path) is None


def test_singleton_lock_legacy_stale_on_reused_pid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Legacy pid-only lock + a live process that is NOT a daemon (reused
    PID) → stale → acquire."""
    _write_lock(tmp_path, "99999")
    monkeypatch.setattr(_dispatcher, "_pid_alive", lambda pid: True)
    monkeypatch.setattr(_dispatcher, "_cmdline_is_daemon", lambda pid: False)
    assert _dispatcher._acquire_singleton_lock(tmp_path) is not None


def test_singleton_lock_legacy_conservative_when_cmdline_unreadable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Legacy lock + live PID whose cmdline can't be read (None) → cannot
    prove it's a reused PID, so conservatively block (never double-start)."""
    _write_lock(tmp_path, "99999")
    monkeypatch.setattr(_dispatcher, "_pid_alive", lambda pid: True)
    monkeypatch.setattr(_dispatcher, "_cmdline_is_daemon", lambda pid: None)
    assert _dispatcher._acquire_singleton_lock(tmp_path) is None
