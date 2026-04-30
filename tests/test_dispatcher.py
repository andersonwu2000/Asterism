"""dispatcher.next_worker_kind + cascade_one state transitions."""
from __future__ import annotations

import sqlite3

import pytest

from Tooling import db
from Tooling.dispatcher import next_worker_kind, cascade_one, SHELVE_THRESHOLD


# ---------------------------------------------------------------------
# next_worker_kind
# ---------------------------------------------------------------------

def _fake_goal(*, difficulty: int, attempts: int) -> dict:
    return {"difficulty": difficulty, "attempts": attempts}


def test_next_worker_kind_high_difficulty() -> None:
    assert next_worker_kind(_fake_goal(difficulty=5, attempts=0)) == "Backward"
    assert next_worker_kind(_fake_goal(difficulty=4, attempts=0)) == "Backward"


def test_next_worker_kind_easy_first_attempts() -> None:
    assert next_worker_kind(_fake_goal(difficulty=2, attempts=0)) == "Builder"
    assert next_worker_kind(_fake_goal(difficulty=1, attempts=2)) == "Builder"


def test_next_worker_kind_easy_after_two_attempts() -> None:
    assert next_worker_kind(_fake_goal(difficulty=2, attempts=3)) == "Backward"


# ---------------------------------------------------------------------
# cascade_one — Builder
# ---------------------------------------------------------------------

def _seed_goal(conn: sqlite3.Connection, *, problem: str = "p",
               difficulty: int = 2) -> int:
    conn.execute(
        "INSERT INTO problems (name, manifest_path, created_at) VALUES (?, ?, ?)",
        (problem, "Problems/p/Manifest.md", db.now()),
    )
    return db.insert_goal(
        conn, problem=problem, slug="main", lean_path="Problems/p/Root.lean",
        statement="T", origin="root", difficulty=difficulty,
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
# cascade_one — Backward
# ---------------------------------------------------------------------

def test_cascade_backward_success_marks_attempting(conn: sqlite3.Connection) -> None:
    gid = _seed_goal(conn)
    cascade_one(conn, pipeline_id="pid", kind="Backward",
                target_id=str(gid), target_kind="Goal", outcome="success")
    row = db.get_goal(conn, gid)
    assert row["status"] == "attempting"


def test_cascade_backward_failed_increments(conn: sqlite3.Connection) -> None:
    gid = _seed_goal(conn)
    cascade_one(conn, pipeline_id="pid", kind="Backward",
                target_id=str(gid), target_kind="Goal", outcome="failed")
    row = db.get_goal(conn, gid)
    assert row["attempts"] == 1


# ---------------------------------------------------------------------
# cascade_one — Verify
# ---------------------------------------------------------------------

def _seed_strategy(conn: sqlite3.Connection, goal_id: int) -> int:
    return db.insert_strategy(
        conn, goal_id=goal_id, lean_path=f"Problems/p/Root_{goal_id}.lean",
        created_by="pid",
    )


def test_cascade_verify_proved_succeeds_strategy_and_goal(
    conn: sqlite3.Connection,
) -> None:
    gid = _seed_goal(conn)
    sid = _seed_strategy(conn, gid)
    cascade_one(conn, pipeline_id="pid", kind="Verify",
                target_id=str(sid), target_kind="Strategy", outcome="proved")
    s = conn.execute("SELECT status FROM strategies WHERE id = ?", (sid,)).fetchone()
    g = db.get_goal(conn, gid)
    assert s["status"] == "succeeded"
    assert g["status"] == "proved"


def test_cascade_verify_failed_marks_strategy_dead(
    conn: sqlite3.Connection,
) -> None:
    gid = _seed_goal(conn)
    sid = _seed_strategy(conn, gid)
    cascade_one(conn, pipeline_id="pid", kind="Verify",
                target_id=str(sid), target_kind="Strategy", outcome="failed")
    s = conn.execute("SELECT status FROM strategies WHERE id = ?", (sid,)).fetchone()
    g = db.get_goal(conn, gid)
    assert s["status"] == "dead"
    assert g["attempts"] == 1


def test_cascade_verify_failed_reopens_attempting_goal(
    conn: sqlite3.Connection,
) -> None:
    """After last live strategy dies, goal must return to 'open' so a fresh
    Backward can be dispatched. Otherwise goal is stuck 'attempting'."""
    gid = _seed_goal(conn)
    db.update_goal_status(conn, gid, "attempting")
    sid = _seed_strategy(conn, gid)
    cascade_one(conn, pipeline_id="pid", kind="Verify",
                target_id=str(sid), target_kind="Strategy", outcome="failed")
    g = db.get_goal(conn, gid)
    assert g["status"] == "open"


def test_cascade_verify_failed_keeps_attempting_when_other_strategies_live(
    conn: sqlite3.Connection,
) -> None:
    gid = _seed_goal(conn)
    db.update_goal_status(conn, gid, "attempting")
    sid1 = _seed_strategy(conn, gid)
    sid2 = db.insert_strategy(
        conn, goal_id=gid, lean_path=f"Problems/p/Root_{gid}.lean",
        created_by="pid",
    )
    cascade_one(conn, pipeline_id="pid", kind="Verify",
                target_id=str(sid1), target_kind="Strategy", outcome="failed")
    g = db.get_goal(conn, gid)
    assert g["status"] == "attempting"  # sid2 still live


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


def test_cascade_verify_proved_supersedes_siblings(
    conn: sqlite3.Connection,
) -> None:
    gid = _seed_goal(conn)
    sid_winner = db.insert_strategy(conn, goal_id=gid,
                                    lean_path="Problems/p/Root.lean",
                                    created_by="pid-w",
                                    scratch_path="proofs/_strategy_s1.lean")
    sid_loser1 = db.insert_strategy(conn, goal_id=gid,
                                    lean_path="Problems/p/Root.lean",
                                    created_by="pid-l1")
    sid_loser2 = db.insert_strategy(conn, goal_id=gid,
                                    lean_path="Problems/p/Root.lean",
                                    created_by="pid-l2")
    cascade_one(conn, pipeline_id="pid-w", kind="Verify",
                target_id=str(sid_winner), target_kind="Strategy",
                outcome="proved")
    statuses = {
        sid: conn.execute("SELECT status FROM strategies WHERE id = ?",
                          (sid,)).fetchone()["status"]
        for sid in (sid_winner, sid_loser1, sid_loser2)
    }
    assert statuses[sid_winner] == "succeeded"
    assert statuses[sid_loser1] == "superseded"
    assert statuses[sid_loser2] == "superseded"
    assert db.get_goal(conn, gid)["status"] == "proved"


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
        statement="T", origin="backward", difficulty=3, depth=1,
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
    from Tooling.dispatcher import _recover_at_startup
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
    from Tooling.dispatcher import _recover_at_startup
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


def test_recover_at_startup_clears_orphan_attempts_dirs(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """F2: daemon kill bypasses WorkArea cleanup; child claude subprocesses
    can keep writing to dead parent's dir. Startup must rmtree everything
    in .attempts/ (it's pure transient state; any pre-existing dir is
    stale by definition)."""
    from Tooling.dispatcher import _recover_at_startup
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
    from Tooling.dispatcher import _recover_at_startup
    _recover_at_startup(conn)  # workspace=None default
    # No assertion needed; reaching here means no exception.


def test_recover_at_startup_restores_backup_when_goal_not_proved(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """F3: a `.lean.backup` left by a killed Builder/Verify means the
    pipeline didn't commit success. Goal is still open in DB. The
    current .lean may hold a half-applied patch; restore the backup."""
    from Tooling.dispatcher import _recover_at_startup
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
    from Tooling.dispatcher import _recover_at_startup
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
    from Tooling.dispatcher import _recover_at_startup
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
    from Tooling.dispatcher import _recover_at_startup
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
        statement="T", origin="root", difficulty=4,
    )


def test_recover_at_startup_reopens_stuck_attempting_goals(
    conn: sqlite3.Connection,
) -> None:
    """Goal in 'attempting' with no surviving 'proposed' strategy is stuck
    — bfs_refill won't dispatch it. Recovery must reset to 'open'.
    Goals with at least one 'proposed' strategy are left alone."""
    from Tooling.dispatcher import _recover_at_startup
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
        origin="root", difficulty=4,
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
        statement="T", origin="backward", difficulty=3, depth=1,
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
        statement="T", origin="backward", difficulty=2, depth=2,
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


def test_bfs_refill_or_fanout_for_backward(conn: sqlite3.Connection) -> None:
    """For an open goal whose next worker is Backward, bfs_refill must
    enqueue up to or_fanout entries (running set empty here)."""
    from Tooling.dispatcher import bfs_refill
    gid = _seed_goal(conn, difficulty=4)  # difficulty>=4 → Backward
    bfs_refill(conn, running=set(), or_fanout=3)
    assert db.queue_count(conn, target_id=str(gid), kind="Backward") == 3


def test_bfs_refill_builder_capped_at_one(conn: sqlite3.Connection) -> None:
    """Builder is single-attempt-per-goal even with high fanout."""
    from Tooling.dispatcher import bfs_refill
    gid = _seed_goal(conn, difficulty=2)  # difficulty<4, attempts=0 → Builder
    bfs_refill(conn, running=set(), or_fanout=5)
    assert db.queue_count(conn, target_id=str(gid), kind="Builder") == 1


def test_strategies_ready_for_verify_excludes_proved_goal(
    conn: sqlite3.Connection,
) -> None:
    """W6 fix: a strategy whose own goal is already proved (by sibling
    OR strategy) must NOT be returned as ready, even if its sub-goals
    are all proved. Prevents the Verify-thrashing loop seen in
    compactness smoke."""
    gid = _seed_goal(conn)
    sid = db.insert_strategy(conn, goal_id=gid,
                             lean_path="Problems/p/Root.lean",
                             created_by="pid")
    # Add a proved sub-goal so the EXISTS clause is satisfied.
    sub_gid = db.insert_goal(
        conn, problem="p", slug="proved_sub",
        lean_path="Problems/p/proofs/L_proved_sub.lean",
        statement="T", origin="backward", difficulty=1, depth=1,
    )
    db.update_goal_status(conn, sub_gid, "proved")
    db.link_subgoal(conn, strategy_id=sid, subgoal_id=sub_gid, position=0)

    # While goal is open: ready
    assert any(s["id"] == sid for s in db.strategies_ready_for_verify(conn))

    # Once goal is proved (by sibling): NOT ready
    db.update_goal_status(conn, gid, "proved")
    assert not any(s["id"] == sid for s in db.strategies_ready_for_verify(conn))


def test_cascade_finalizes_superseded_when_goal_already_proved(
    conn: sqlite3.Connection,
) -> None:
    """W6 fix: cascade no-op entry should ALSO transition a still-'proposed'
    strategy to 'superseded' when its goal is already proved. Without
    this, the strategy stays 'proposed' and bfs_refill thrashes."""
    gid = _seed_goal(conn)
    db.update_goal_status(conn, gid, "proved")
    sid = db.insert_strategy(conn, goal_id=gid,
                             lean_path="Problems/p/Root.lean",
                             created_by="pid")
    cascade_one(conn, pipeline_id="late", kind="Verify",
                target_id=str(sid), target_kind="Strategy", outcome="failed")
    s = conn.execute("SELECT status FROM strategies WHERE id = ?",
                     (sid,)).fetchone()
    assert s["status"] == "superseded"
