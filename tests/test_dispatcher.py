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
        "INSERT INTO problems (name, manifest_path, created_at) VALUES (?, ?, ?)",
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


def test_cascade_builder_shelves_at_threshold(conn: sqlite3.Connection) -> None:
    gid = _seed_goal(conn)
    for _ in range(SHELVE_THRESHOLD):
        cascade_one(conn, pipeline_id="pid", kind="Builder",
                    target_id=str(gid), target_kind="Goal", outcome="failed")
    row = db.get_goal(conn, gid)
    assert row["status"] == "shelved"
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

def test_subgoal_shelve_kills_parent_strategy_and_reopens_goal(
    conn: sqlite3.Connection,
) -> None:
    """F12: when a sub-goal hits SHELVE_THRESHOLD, parent strategies
    that depend on it can never become ready_for_verify (require all
    sub-goals 'proved'). Cascade should kill them so the grandparent
    goal is no longer blocked by zombies.

    Grandparent → strategy → {proved-sub, doomed-sub}.
    Doomed sub-goal accumulates failures and shelves at attempts=7.
    Strategy should die; grandparent should reopen if it has no other
    live strategy."""
    grand = _seed_goal(conn, problem="p")
    db.update_goal_status(conn, grand, "attempting")

    proved_sub = db.insert_goal(
        conn, problem="p", slug="proved_sub",
        lean_path="Problems/p/proofs/L_proved_sub.lean",
        statement="T", origin="backward", depth=1,
    )
    db.update_goal_status(conn, proved_sub, "proved")

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
    db.link_subgoal(conn, strategy_id=sid, subgoal_id=proved_sub, position=0)
    db.link_subgoal(conn, strategy_id=sid, subgoal_id=doomed_sub, position=1)

    # Push doomed_sub to SHELVE_THRESHOLD via Builder failures.
    for _ in range(SHELVE_THRESHOLD):
        cascade_one(conn, pipeline_id="pid", kind="Builder",
                    target_id=str(doomed_sub), target_kind="Goal",
                    outcome="failed")

    # Doomed sub-goal shelved
    assert db.get_goal(conn, doomed_sub)["status"] == "shelved"
    # Parent strategy died (no longer 'proposed')
    assert conn.execute(
        "SELECT status FROM strategies WHERE id = ?", (sid,),
    ).fetchone()["status"] == "dead"
    # Grandparent reopened (no live strategy left)
    assert db.get_goal(conn, grand)["status"] == "open"
    # F37 — grandparent attempts incremented by 1, so passive Backward
    # retries can't loop forever
    assert db.get_goal(conn, grand)["attempts"] == 1


def test_subgoal_shelve_cascades_grand_when_at_threshold(
    conn: sqlite3.Connection,
) -> None:
    """F37 — when sub-goal shelve triggers parent strategy death AND the
    grandparent's incremented attempts reach SHELVE_THRESHOLD, the
    grandparent itself shelves and propagates further up."""
    grand = _seed_goal(conn, problem="p")
    db.update_goal_status(conn, grand, "attempting")
    # Pre-load grand attempts to one short of SHELVE_THRESHOLD so the
    # increment from the cascade pushes it over.
    conn.execute("UPDATE goals SET attempts = ? WHERE id = ?",
                 (SHELVE_THRESHOLD - 1, grand))
    conn.commit()

    doomed_sub = db.insert_goal(
        conn, problem="p", slug="doomed_for_grand_cascade",
        lean_path="Problems/p/proofs/L_doomed_grand.lean",
        statement="T", origin="backward", depth=1,
    )
    sid = db.insert_strategy(
        conn, goal_id=grand,
        lean_path="Problems/p/Root.lean",
        scratch_path="Problems/p/proofs/_strategy_grand.lean",
        created_by="pid",
    )
    db.link_subgoal(conn, strategy_id=sid, subgoal_id=doomed_sub, position=0)

    for _ in range(SHELVE_THRESHOLD):
        cascade_one(conn, pipeline_id="pid", kind="Builder",
                    target_id=str(doomed_sub), target_kind="Goal",
                    outcome="failed")

    assert db.get_goal(conn, doomed_sub)["status"] == "shelved"
    assert db.get_goal(conn, grand)["status"] == "shelved"
    assert db.get_goal(conn, grand)["attempts"] == SHELVE_THRESHOLD


def test_subgoal_shelve_keeps_goal_attempting_when_other_strategy_alive(
    conn: sqlite3.Connection,
) -> None:
    """F12: if grandparent has another live strategy after one dies,
    don't reopen — the alive strategy may still verify."""
    grand = _seed_goal(conn, problem="p")
    db.update_goal_status(conn, grand, "attempting")

    doomed_sub = db.insert_goal(
        conn, problem="p", slug="doomed_sub2",
        lean_path="Problems/p/proofs/L_doomed_sub2.lean",
        statement="T", origin="backward", depth=1,
    )

    # Two strategies on grand; only s1 includes doomed_sub
    s1 = db.insert_strategy(conn, goal_id=grand,
                            lean_path="Problems/p/Root.lean",
                            scratch_path="Problems/p/proofs/_strategy_s1.lean",
                            created_by="pid1")
    db.link_subgoal(conn, strategy_id=s1, subgoal_id=doomed_sub, position=0)

    s2 = db.insert_strategy(conn, goal_id=grand,
                            lean_path="Problems/p/Root.lean",
                            scratch_path="Problems/p/proofs/_strategy_s2.lean",
                            created_by="pid2")
    # s2's sub-goals not touched

    for _ in range(SHELVE_THRESHOLD):
        cascade_one(conn, pipeline_id="pid", kind="Builder",
                    target_id=str(doomed_sub), target_kind="Goal",
                    outcome="failed")

    assert conn.execute(
        "SELECT status FROM strategies WHERE id = ?", (s1,),
    ).fetchone()["status"] == "dead"
    assert conn.execute(
        "SELECT status FROM strategies WHERE id = ?", (s2,),
    ).fetchone()["status"] == "proposed"
    # Grandparent stays attempting (s2 still alive)
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
# F16 — goal-shelve symmetric cascade: kill its own strategies
# ---------------------------------------------------------------------

def test_goal_shelve_kills_own_strategies(
    conn: sqlite3.Connection,
) -> None:
    """F16: when goal X shelves, strategies for proving X are moot.
    They must transition 'proposed' → 'dead' so DB invariant holds:
    strategy.status='proposed' implies parent goal alive."""
    gid = _seed_goal(conn)

    # Two proposed strategies on this goal
    s1 = db.insert_strategy(conn, goal_id=gid,
                            lean_path="Problems/p/Root.lean",
                            scratch_path="Problems/p/proofs/_strategy_a.lean",
                            created_by="pid1")
    s2 = db.insert_strategy(conn, goal_id=gid,
                            lean_path="Problems/p/Root.lean",
                            scratch_path="Problems/p/proofs/_strategy_b.lean",
                            created_by="pid2")

    # Push goal itself to SHELVE_THRESHOLD via Backward failures
    for _ in range(SHELVE_THRESHOLD):
        cascade_one(conn, pipeline_id="pid", kind="Backward",
                    target_id=str(gid), target_kind="Goal",
                    outcome="failed")

    assert db.get_goal(conn, gid)["status"] == "shelved"
    # Both strategies on the shelved goal should now be dead
    assert conn.execute(
        "SELECT status FROM strategies WHERE id = ?", (s1,),
    ).fetchone()["status"] == "dead"
    assert conn.execute(
        "SELECT status FROM strategies WHERE id = ?", (s2,),
    ).fetchone()["status"] == "dead"


def test_goal_shelve_combined_upward_and_inward_cascade(
    conn: sqlite3.Connection,
) -> None:
    """F12 + F16 together: a goal that is both (a) sub-goal of a parent
    strategy and (b) has its own strategies must propagate in both
    directions when it shelves."""
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

    for _ in range(SHELVE_THRESHOLD):
        cascade_one(conn, pipeline_id="pid", kind="Backward",
                    target_id=str(middle), target_kind="Goal",
                    outcome="failed")

    # F12 — parent strategy killed (used middle as sub)
    assert conn.execute(
        "SELECT status FROM strategies WHERE id = ?", (parent_strat,),
    ).fetchone()["status"] == "dead"
    # F16 — middle's own strategy killed (middle is shelved)
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
        "INSERT INTO problems (name, manifest_path, created_at) VALUES (?, ?, ?)",
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
        "INSERT INTO problems (name, manifest_path, created_at) "
        "VALUES (?, ?, ?)",
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
        "INSERT INTO problems (name, manifest_path, created_at) "
        "VALUES (?, ?, ?)",
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


def test_open_goals_scope_filter(conn: sqlite3.Connection) -> None:
    """Underlying `db.open_goals(scope=...)` SQL filter. Direct unit test
    so the scope plumbing is covered even if bfs_refill restructures."""
    _seed_goal(conn, problem="sg")
    conn.execute(
        "INSERT INTO problems (name, manifest_path, created_at) "
        "VALUES (?, ?, ?)",
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


# F56 — `cascade_one(kind="Verify")` no longer exists. The W6
# "stale proposed strategy on a proved goal" finalization is handled
# by `verify.verify_strategy` returning "superseded"; see
# `tests/test_verify.py`.
