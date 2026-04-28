"""Unit + integration tests for P3 C24 blocked_pipelines mechanism."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from Tooling.db.connect import connect, init_schema
from Tooling.stages.failure_archive import (
    N_BLOCK_AFTER_FAILURES,
    archive_check,
    archive_ih_trap,
)
from Tooling.subsystems.blocked_pipelines import (
    block_pipeline,
    get_blocked_pipelines,
    is_blocked,
    unblock_pipeline,
)


_NOW = "2026-01-01T00:00:00+00:00"


@pytest.fixture
def db(tmp_path: Path) -> sqlite3.Connection:
    conn = connect(tmp_path / "asterism.db")
    init_schema(conn)
    yield conn
    conn.close()


def _insert_goal(conn, *, slug="g", problem="ex"):
    conn.execute(
        "INSERT INTO goals "
        "(problem, slug, lean_path, origin, kind, status, "
        "commit_state, created_at, updated_at) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (problem, slug, f"path/{slug}.lean", "root", "theorem", "open",
         "live", _NOW, _NOW),
    )
    conn.commit()
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def _insert_pipeline(conn, *, pid="pipe-x", kind="Backward", target_id="0"):
    conn.execute(
        "INSERT OR IGNORE INTO pipelines "
        "(id, kind, runtime, target_id, target_kind, status, started_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (pid, kind, "atomic", target_id, "Goal", "succeeded", _NOW),
    )
    conn.commit()
    return pid


def _insert_dead_attempt(conn, *, target_id, pipeline_kind, outcome,
                         pipeline_id="pipe-x", ts=None):
    _insert_pipeline(conn, pid=pipeline_id, kind=pipeline_kind)
    conn.execute(
        "INSERT INTO dead_attempts "
        "(target_id, target_kind, pipeline_id, pipeline_kind, "
        "outcome, reason_summary, ts) "
        "VALUES (?,?,?,?,?,?,?)",
        (str(target_id), "Goal", pipeline_id, pipeline_kind, outcome,
         f"reason for {outcome}", ts or _NOW),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# blocked_pipelines low-level
# ---------------------------------------------------------------------------


class TestBlockPipeline:
    def test_block_adds_to_empty_list(self, db):
        gid = _insert_goal(db)
        added = block_pipeline(db, gid, "Backward")
        assert added is True
        assert get_blocked_pipelines(db, gid) == ["Backward"]

    def test_block_idempotent(self, db):
        gid = _insert_goal(db)
        assert block_pipeline(db, gid, "Backward") is True
        assert block_pipeline(db, gid, "Backward") is False
        assert get_blocked_pipelines(db, gid) == ["Backward"]

    def test_block_appends_distinct(self, db):
        gid = _insert_goal(db)
        block_pipeline(db, gid, "Backward")
        block_pipeline(db, gid, "Builder")
        assert set(get_blocked_pipelines(db, gid)) == {"Backward", "Builder"}

    def test_invalid_pipeline_kind_raises(self, db):
        gid = _insert_goal(db)
        with pytest.raises(ValueError, match="unknown pipeline_kind"):
            block_pipeline(db, gid, "BogusPipeline")

    def test_pending_goal_not_updated(self, db):
        """Spec §1 commit protocol: only live rows affected.

        C24 R3 HIGH-1 fix: block_pipeline now correctly returns False (was
        True) when target is pending — UPDATE 0 rows under atomic SQL.
        """
        db.execute(
            "INSERT INTO goals (problem, slug, lean_path, origin, kind, status, "
            "commit_state, created_at, updated_at) "
            "VALUES ('ex', 'pg', 'p.lean', 'root', 'theorem', 'open', "
            "'pending', ?, ?)",
            (_NOW, _NOW),
        )
        db.commit()
        gid = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        # block_pipeline returns False (rowcount == 0)
        assert block_pipeline(db, gid, "Backward") is False
        # get_blocked_pipelines also filters live — won't see it
        assert get_blocked_pipelines(db, gid) == []

    def test_corrupt_json_raises(self, db):
        """C24 R3 MED-2: silent-failure red line — corrupt JSON raises ValueError
        rather than silently returning []."""
        gid = _insert_goal(db)
        # Manually inject corrupt JSON
        with db:
            db.execute(
                "UPDATE goals SET blocked_pipelines = 'not valid json {{{' "
                "WHERE id = ?",
                (gid,),
            )
        with pytest.raises(ValueError, match="JSON corrupt"):
            get_blocked_pipelines(db, gid)

    def test_non_list_json_raises(self, db):
        """JSON parses OK but isn't a list — also raises (schema invariant)."""
        gid = _insert_goal(db)
        with db:
            db.execute(
                "UPDATE goals SET blocked_pipelines = ? WHERE id = ?",
                (json.dumps({"not": "a list"}), gid),
            )
        with pytest.raises(ValueError, match="not a JSON list"):
            get_blocked_pipelines(db, gid)


class TestIsBlocked:
    def test_returns_true_after_block(self, db):
        gid = _insert_goal(db)
        block_pipeline(db, gid, "Backward")
        assert is_blocked(db, gid, "Backward") is True
        assert is_blocked(db, gid, "Builder") is False


class TestUnblockPipeline:
    def test_unblock_specific(self, db):
        gid = _insert_goal(db)
        block_pipeline(db, gid, "Backward")
        block_pipeline(db, gid, "Builder")
        removed = unblock_pipeline(db, gid, "Backward")
        assert removed == 1
        assert get_blocked_pipelines(db, gid) == ["Builder"]

    def test_unblock_all(self, db):
        gid = _insert_goal(db)
        block_pipeline(db, gid, "Backward")
        block_pipeline(db, gid, "Builder")
        removed = unblock_pipeline(db, gid, None)
        assert removed == 2
        assert get_blocked_pipelines(db, gid) == []

    def test_unblock_missing_is_noop(self, db):
        gid = _insert_goal(db)
        assert unblock_pipeline(db, gid, "Backward") == 0


# ---------------------------------------------------------------------------
# failure_archive: generic N=5
# ---------------------------------------------------------------------------


class TestArchiveCheckGeneric:
    def test_below_threshold_does_not_block(self, db):
        gid = _insert_goal(db)
        for _ in range(N_BLOCK_AFTER_FAILURES - 1):
            _insert_dead_attempt(db, target_id=gid,
                                  pipeline_kind="Backward", outcome="exhausted")
        blocked = archive_check(db, gid, "Backward")
        assert blocked is False
        assert is_blocked(db, gid, "Backward") is False

    def test_at_threshold_blocks(self, db):
        gid = _insert_goal(db)
        for _ in range(N_BLOCK_AFTER_FAILURES):
            _insert_dead_attempt(db, target_id=gid,
                                  pipeline_kind="Backward", outcome="exhausted")
        blocked = archive_check(db, gid, "Backward")
        assert blocked is True
        assert is_blocked(db, gid, "Backward") is True

    def test_mixed_outcomes_count_only_exhausted_unproductive(self, db):
        """spec phase3 §In: needs_decomp / bad_goal NOT counted."""
        gid = _insert_goal(db)
        # 3 exhausted + 2 unproductive = 5 (should block)
        for _ in range(3):
            _insert_dead_attempt(db, target_id=gid,
                                  pipeline_kind="Backward", outcome="exhausted")
        for _ in range(2):
            _insert_dead_attempt(db, target_id=gid,
                                  pipeline_kind="Backward",
                                  outcome="unproductive")
        # Plus 5 needs_decomp (must NOT count)
        for _ in range(5):
            _insert_dead_attempt(db, target_id=gid,
                                  pipeline_kind="Backward",
                                  outcome="needs_decomp")
        blocked = archive_check(db, gid, "Backward")
        assert blocked is True

    def test_other_pipeline_kind_separate_count(self, db):
        gid = _insert_goal(db)
        for _ in range(N_BLOCK_AFTER_FAILURES):
            _insert_dead_attempt(db, target_id=gid,
                                  pipeline_kind="Builder", outcome="exhausted")
        # 5 Builder failures should not block Backward
        assert archive_check(db, gid, "Backward") is False
        # But should block Builder
        assert archive_check(db, gid, "Builder") is True

    def test_already_blocked_no_op(self, db):
        gid = _insert_goal(db)
        block_pipeline(db, gid, "Backward")
        # Even with high count, archive_check returns False (no new block)
        for _ in range(N_BLOCK_AFTER_FAILURES * 2):
            _insert_dead_attempt(db, target_id=gid,
                                  pipeline_kind="Backward", outcome="exhausted")
        assert archive_check(db, gid, "Backward") is False


# ---------------------------------------------------------------------------
# failure_archive: IH-trap special case
# ---------------------------------------------------------------------------


def _insert_strategy(conn, *, goal_id, similarity, sid_label="s_x"):
    conn.execute(
        "INSERT INTO strategies "
        "(goal_id, lean_path, status, commit_state, "
        "parent_subgoal_max_similarity, created_at) "
        "VALUES (?,?,?,?,?,?)",
        (goal_id, f"path/{sid_label}.lean", "proposed", "live",
         similarity, _NOW),
    )
    conn.commit()
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


class TestArchiveIhTrap:
    def test_blocks_when_2_unproductive_plus_high_similarity(self, db):
        gid = _insert_goal(db)
        _insert_dead_attempt(db, target_id=gid, pipeline_kind="Backward",
                              outcome="unproductive", ts="2026-01-01T00:00:01+00:00")
        _insert_dead_attempt(db, target_id=gid, pipeline_kind="Backward",
                              outcome="unproductive", ts="2026-01-01T00:00:02+00:00")
        _insert_strategy(db, goal_id=gid, similarity=0.9)  # >= 0.85
        blocked = archive_ih_trap(db, gid, "Backward")
        assert blocked is True
        assert is_blocked(db, gid, "Backward") is True

    def test_does_not_block_when_similarity_low(self, db):
        gid = _insert_goal(db)
        _insert_dead_attempt(db, target_id=gid, pipeline_kind="Backward",
                              outcome="unproductive")
        _insert_dead_attempt(db, target_id=gid, pipeline_kind="Backward",
                              outcome="unproductive",
                              ts="2026-01-01T00:00:02+00:00")
        _insert_strategy(db, goal_id=gid, similarity=0.5)  # < 0.85
        assert archive_ih_trap(db, gid, "Backward") is False

    def test_does_not_block_when_only_one_unproductive(self, db):
        gid = _insert_goal(db)
        _insert_dead_attempt(db, target_id=gid, pipeline_kind="Backward",
                              outcome="unproductive")
        _insert_strategy(db, goal_id=gid, similarity=0.9)
        assert archive_ih_trap(db, gid, "Backward") is False

    def test_does_not_block_when_recent_outcome_is_exhausted(self, db):
        """Mixed outcomes (one exhausted) breaks the streak."""
        gid = _insert_goal(db)
        _insert_dead_attempt(db, target_id=gid, pipeline_kind="Backward",
                              outcome="unproductive",
                              ts="2026-01-01T00:00:01+00:00")
        _insert_dead_attempt(db, target_id=gid, pipeline_kind="Backward",
                              outcome="exhausted",
                              ts="2026-01-01T00:00:02+00:00")
        _insert_strategy(db, goal_id=gid, similarity=0.9)
        assert archive_ih_trap(db, gid, "Backward") is False


# ---------------------------------------------------------------------------
# Scheduler integration: BFS filter + cascade hook
# ---------------------------------------------------------------------------


class TestSchedulerBFSFilter:
    def test_bfs_skips_blocked_backward(self, db, tmp_path):
        from Tooling.scheduler import Reactor, ReactorConfig
        gid = _insert_goal(db, slug="blocked_g")
        block_pipeline(db, gid, "Backward")

        reactor = Reactor(str(tmp_path / "asterism.db"),
                          ReactorConfig(base_dir=str(tmp_path)))
        reactor.conn = db
        reactor._run_structural_refill()

        kinds = [r[0] for r in db.execute(
            "SELECT kind FROM queue WHERE target_id=?", (str(gid),)
        ).fetchall()]
        assert "Backward" not in kinds


class TestSchedulerCascadeBackwardHook:
    def test_exhausted_records_dead_attempt(self, db, tmp_path):
        """C25: cascade writes dead_attempts on non-success (in-memory
        _failure_count removed; persistent block is the canonical signal)."""
        from Tooling.pipelines.backward import BackwardResult
        from Tooling.scheduler import Reactor, ReactorConfig
        gid = _insert_goal(db, slug="cascade_g")
        _insert_pipeline(db, pid="pipe-bw", kind="Backward",
                          target_id=str(gid))

        reactor = Reactor(str(tmp_path / "asterism.db"),
                          ReactorConfig(base_dir=str(tmp_path)))
        reactor.conn = db
        reactor._cascade_backward(gid, BackwardResult(outcome="exhausted"))

        rows = db.execute(
            "SELECT outcome FROM dead_attempts WHERE target_id=? AND pipeline_kind='Backward'",
            (str(gid),),
        ).fetchall()
        assert len(rows) == 1
        assert rows[0][0] == "exhausted"

    def test_5th_exhausted_blocks_via_failure_archive(self, db, tmp_path):
        from Tooling.pipelines.backward import BackwardResult
        from Tooling.scheduler import Reactor, ReactorConfig
        gid = _insert_goal(db, slug="block_at_5")
        _insert_pipeline(db, pid="pipe-bw5", kind="Backward",
                          target_id=str(gid))

        reactor = Reactor(str(tmp_path / "asterism.db"),
                          ReactorConfig(base_dir=str(tmp_path)))
        reactor.conn = db
        for _ in range(N_BLOCK_AFTER_FAILURES):
            reactor._cascade_backward(gid, BackwardResult(outcome="exhausted"))

        assert is_blocked(db, gid, "Backward") is True

    def test_missing_pipeline_id_raises_fatal(self, db, tmp_path):
        """C24 R3 MED-3: orphan Backward cascade (no Backward pipeline row)
        is an invariant violation — must emit fatal + raise FatalError, not
        silently skip the dead_attempts INSERT."""
        from Tooling.pipelines.backward import BackwardResult
        from Tooling.scheduler import FatalError, Reactor, ReactorConfig
        gid = _insert_goal(db, slug="orphan_cascade")
        # NO _insert_pipeline call — orphan cascade

        reactor = Reactor(str(tmp_path / "asterism.db"),
                          ReactorConfig(base_dir=str(tmp_path)))
        reactor.conn = db
        with pytest.raises(FatalError, match="backward_failure_no_pipeline_id"):
            reactor._cascade_backward(gid,
                                       BackwardResult(outcome="exhausted"))


class TestSchedulerCascadeBuilderHook:
    """C24 R3 MED-1: Builder cascade also triggers archive_check (phase3 §In
    line 37 字面 "Backward / Builder 都會觸發")."""

    def test_5th_builder_exhausted_blocks(self, db, tmp_path):
        from Tooling.pipelines.builder import BuilderResult
        from Tooling.scheduler import Reactor, ReactorConfig
        gid = _insert_goal(db, slug="builder_block")
        # Insert a strategy + 5 dead_attempts for it
        db.execute(
            "INSERT INTO strategies "
            "(goal_id, lean_path, status, commit_state, created_at) "
            "VALUES (?,?,?,?,?)",
            (gid, "path/s.lean", "proposed", "live", _NOW),
        )
        db.commit()
        sid = db.execute("SELECT last_insert_rowid()").fetchone()[0]

        # Pre-seed Goal-side dead_attempts for Builder (real flow has these
        # written by Builder._record_dead_attempts at strategy granularity;
        # archive_check counts target_kind='Goal' so we seed those here).
        for _ in range(N_BLOCK_AFTER_FAILURES):
            _insert_dead_attempt(db, target_id=gid,
                                  pipeline_kind="Builder",
                                  outcome="exhausted")

        reactor = Reactor(str(tmp_path / "asterism.db"),
                          ReactorConfig(base_dir=str(tmp_path)))
        reactor.conn = db
        # Trigger _cascade_builder with non-proved outcome
        reactor._cascade_builder(sid, BuilderResult(outcome="exhausted"))

        assert is_blocked(db, gid, "Builder") is True


class TestAtomicWriteRaceSafety:
    """C24 R3 HIGH-1: block_pipeline now uses atomic SQL json_insert with
    json_each NOT EXISTS dedup. Verify rowcount-based idempotence."""

    def test_concurrent_distinct_kinds_both_persist(self, db):
        """Two distinct kinds blocked back-to-back: both persist (was the
        spec failure mode in the Python read-modify-write strategy A2)."""
        gid = _insert_goal(db, slug="atomic_g")
        a = block_pipeline(db, gid, "Backward")
        b = block_pipeline(db, gid, "Builder")
        assert a is True and b is True
        result = get_blocked_pipelines(db, gid)
        assert set(result) == {"Backward", "Builder"}

    def test_idempotent_same_kind_returns_false_second_time(self, db):
        gid = _insert_goal(db, slug="idem_g")
        first = block_pipeline(db, gid, "Backward")
        second = block_pipeline(db, gid, "Backward")
        assert first is True
        assert second is False
        assert get_blocked_pipelines(db, gid) == ["Backward"]
