"""Unit tests for CommitWriter (Tooling/commit.py).

Covers:
  - 6 recovery sub-cases: INSERT × {after_step1, after_step2, after_step3}
                          + UPDATE × same
  - COMMIT_FAULT env hook (3 modes)
  - begin_batch atomicity
"""
from __future__ import annotations

import json
import sqlite3

import pytest

from Tooling.commit import CommitFault, CommitWriter
from Tooling.db.connect import connect, init_schema

NOW = "2026-01-01T00:00:00+00:00"


# ──────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────


@pytest.fixture
def db() -> sqlite3.Connection:
    conn = connect(":memory:")
    init_schema(conn)
    yield conn
    conn.close()


@pytest.fixture
def cw(db: sqlite3.Connection) -> CommitWriter:
    return CommitWriter(db)


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────


def _insert_live_goal(db: sqlite3.Connection, lean_path: str) -> int:
    db.execute(
        "INSERT INTO goals"
        "(problem,slug,lean_path,origin,kind,status,commit_state,created_at,updated_at)"
        " VALUES (?,?,?,?,?,?,?,?,?)",
        ("test", "g", lean_path, "root", "theorem", "open", "live", NOW, NOW),
    )
    db.commit()
    return db.execute("SELECT last_insert_rowid()").fetchone()[0]


def _insert_live_strategy(
    db: sqlite3.Connection, goal_id: int, lean_path: str
) -> int:
    db.execute(
        "INSERT INTO strategies(goal_id,lean_path,status,commit_state,created_at)"
        " VALUES (?,?,?,?,?)",
        (goal_id, lean_path, "proposed", "live", NOW),
    )
    db.commit()
    return db.execute("SELECT last_insert_rowid()").fetchone()[0]


def _goal_data(lean_path: str) -> dict:
    return dict(
        problem="test",
        slug="tgoal",
        lean_path=lean_path,
        origin="root",
        kind="theorem",
        status="open",
    )


def _strat_data(goal_id: int, lean_path: str) -> dict:
    return dict(goal_id=goal_id, lean_path=lean_path, status="proposed")


# ──────────────────────────────────────────────────────────────
# Recovery scan – INSERT cases (goals table)
# ──────────────────────────────────────────────────────────────


class TestRecoverInsert:
    """6 sub-cases: INSERT × {after_step1, after_step2, after_step3}."""

    def test_insert_after_step1_deletes_row(
        self, db: sqlite3.Connection, cw: CommitWriter, tmp_path, monkeypatch
    ) -> None:
        """Crash after step 1 (INSERT pending, file not moved): recover DELETEs row."""
        lean_path = tmp_path / "goal.lean"
        staging = tmp_path / "staging" / "goal.lean"
        staging.parent.mkdir()
        staging.write_text("theorem T : True := trivial")

        monkeypatch.setenv("COMMIT_FAULT", "after_step1")
        with pytest.raises(CommitFault):
            cw.begin("goals", "insert", data=_goal_data(str(lean_path)))
        monkeypatch.delenv("COMMIT_FAULT")

        # Row should be pending in DB, file not yet moved.
        count = db.execute(
            "SELECT COUNT(*) FROM goals WHERE commit_state='pending'"
        ).fetchone()[0]
        assert count == 1
        assert not lean_path.exists()

        result = cw.recover_scan()

        assert db.execute("SELECT COUNT(*) FROM goals").fetchone()[0] == 0
        assert result["goals"] != []  # row was processed

    def test_insert_after_step2_finalizes_row(
        self, db: sqlite3.Connection, cw: CommitWriter, tmp_path, monkeypatch
    ) -> None:
        """Crash after step 2 (file moved, row still pending): recover finalizes."""
        lean_path = tmp_path / "goal.lean"
        staging = tmp_path / "staging" / "goal.lean"
        staging.parent.mkdir()
        staging.write_text("theorem T : True := trivial")

        gid = cw.begin("goals", "insert", data=_goal_data(str(lean_path)))

        monkeypatch.setenv("COMMIT_FAULT", "after_step2")
        with pytest.raises(CommitFault):
            cw.stage_file(staging, lean_path)
        monkeypatch.delenv("COMMIT_FAULT")

        assert lean_path.exists()
        row = db.execute(
            "SELECT commit_state FROM goals WHERE id=?", (gid,)
        ).fetchone()
        assert row[0] == "pending"

        cw.recover_scan()

        row = db.execute(
            "SELECT commit_state, prior_state_snapshot FROM goals WHERE id=?", (gid,)
        ).fetchone()
        assert row[0] == "live"
        assert row[1] is None

    def test_insert_after_step3_is_noop(
        self, db: sqlite3.Connection, cw: CommitWriter, tmp_path, monkeypatch
    ) -> None:
        """Crash after step 3 (commit complete): recover_scan has no pending rows."""
        lean_path = tmp_path / "goal.lean"
        staging = tmp_path / "staging" / "goal.lean"
        staging.parent.mkdir()
        staging.write_text("theorem T : True := trivial")

        gid = cw.begin("goals", "insert", data=_goal_data(str(lean_path)))
        cw.stage_file(staging, lean_path)

        monkeypatch.setenv("COMMIT_FAULT", "after_step3")
        with pytest.raises(CommitFault):
            cw.finalize("goals", gid, {})
        monkeypatch.delenv("COMMIT_FAULT")

        # Row is already live (step 3 TX committed before fault).
        row = db.execute(
            "SELECT commit_state FROM goals WHERE id=?", (gid,)
        ).fetchone()
        assert row[0] == "live"

        result = cw.recover_scan()

        # No pending rows → nothing recovered.
        assert result["goals"] == []
        row = db.execute(
            "SELECT commit_state FROM goals WHERE id=?", (gid,)
        ).fetchone()
        assert row[0] == "live"


# ──────────────────────────────────────────────────────────────
# Recovery scan – UPDATE cases (strategies table)
# ──────────────────────────────────────────────────────────────


class TestRecoverUpdate:
    """6 sub-cases: UPDATE × {after_step1, after_step2, after_step3}."""

    @pytest.fixture
    def live_strat(
        self, db: sqlite3.Connection, tmp_path
    ) -> tuple[int, int]:
        """Returns (goal_id, strat_id) with live rows."""
        goal_lean = tmp_path / "goals" / "g.lean"
        goal_lean.parent.mkdir()
        goal_lean.write_text("-- goal")
        gid = _insert_live_goal(db, str(goal_lean))

        strat_lean = tmp_path / "strat.lean"
        strat_lean.write_text("-- original proof")
        sid = _insert_live_strategy(db, gid, str(strat_lean))
        return gid, sid

    def test_update_after_step1_finalizes_via_lean_exists(
        self,
        db: sqlite3.Connection,
        cw: CommitWriter,
        tmp_path,
        monkeypatch,
        live_strat,
    ) -> None:
        """Step 1 crash with lean_path already on disk (fixture pre-populated):
        recover walks the `lean_exists → finalize` branch, NOT restore-from-snapshot.
        Status equals pre-begin original because step 1 doesn't mutate business
        fields and finalize is invoked with empty final_fields.
        """
        _, sid = live_strat

        monkeypatch.setenv("COMMIT_FAULT", "after_step1")
        with pytest.raises(CommitFault):
            cw.begin("strategies", "update", row_id=sid)
        monkeypatch.delenv("COMMIT_FAULT")

        row = db.execute(
            "SELECT commit_state, prior_state_snapshot FROM strategies WHERE id=?",
            (sid,),
        ).fetchone()
        assert row[0] == "pending"
        assert row[1] is not None
        snap = json.loads(row[1])
        original_status = snap["status"]

        cw.recover_scan()

        row = db.execute(
            "SELECT commit_state, status, prior_state_snapshot FROM strategies WHERE id=?",
            (sid,),
        ).fetchone()
        assert row[0] == "live"
        assert row[1] == original_status
        assert row[2] is None  # snapshot cleared

    def test_update_after_step1_restores_from_snapshot(
        self, db: sqlite3.Connection, cw: CommitWriter, tmp_path
    ) -> None:
        """Restore branch: pending row + snapshot set + lean_path NOT on disk.
        recover_scan walks the `else` branch and restores all fields from
        prior_state_snapshot. Covers phase1 acceptance #4 + impl §1.3 rule 3.
        """
        goal_lean = tmp_path / "goals" / "g.lean"
        goal_lean.parent.mkdir()
        goal_lean.write_text("-- goal")
        gid = _insert_live_goal(db, str(goal_lean))

        # lean_path that does NOT exist on disk – simulates step 1 crash where
        # the staging file was wiped before step 2 ran.
        strat_lean = tmp_path / "missing_strat.lean"
        sid = _insert_live_strategy(db, gid, str(strat_lean))

        # Manually transition row → pending + snapshot, mutating status to a
        # "midflight" value distinct from the original to verify restore.
        snapshot_payload = {
            "id": sid,
            "goal_id": gid,
            "lean_path": str(strat_lean),
            "status": "proposed",
            "commit_state": "live",
            "prior_state_snapshot": None,
            "parent_subgoal_max_similarity": None,
            "created_by": None,
            "created_at": NOW,
        }
        db.execute(
            "UPDATE strategies SET commit_state='pending', "
            "status='in_progress', prior_state_snapshot=? WHERE id=?",
            (json.dumps(snapshot_payload), sid),
        )
        db.commit()

        assert not strat_lean.exists()

        result = cw.recover_scan()

        # Snapshot restored: original status, live, snapshot cleared.
        row = db.execute(
            "SELECT commit_state, status, prior_state_snapshot FROM strategies WHERE id=?",
            (sid,),
        ).fetchone()
        assert row[0] == "live"
        assert row[1] == "proposed"  # restored from snapshot, not the midflight 'in_progress'
        assert row[2] is None
        assert sid in result["strategies"]

    def test_update_after_step2_finalizes_row(
        self,
        db: sqlite3.Connection,
        cw: CommitWriter,
        tmp_path,
        monkeypatch,
        live_strat,
    ) -> None:
        """Crash after step 2 (file moved, row still pending): recover finalizes."""
        _, sid = live_strat
        strat_lean_str = db.execute(
            "SELECT lean_path FROM strategies WHERE id=?", (sid,)
        ).fetchone()[0]
        strat_lean = tmp_path / "strat.lean"  # same as live_strat path

        staging = tmp_path / "staging" / "strat.lean"
        staging.parent.mkdir()
        staging.write_text("-- new proof")

        cw.begin("strategies", "update", row_id=sid)

        monkeypatch.setenv("COMMIT_FAULT", "after_step2")
        with pytest.raises(CommitFault):
            cw.stage_file(staging, strat_lean)
        monkeypatch.delenv("COMMIT_FAULT")

        assert strat_lean.exists()
        row = db.execute(
            "SELECT commit_state FROM strategies WHERE id=?", (sid,)
        ).fetchone()
        assert row[0] == "pending"

        cw.recover_scan()

        row = db.execute(
            "SELECT commit_state, prior_state_snapshot FROM strategies WHERE id=?",
            (sid,),
        ).fetchone()
        assert row[0] == "live"
        assert row[1] is None

    def test_update_after_step3_is_noop(
        self,
        db: sqlite3.Connection,
        cw: CommitWriter,
        tmp_path,
        monkeypatch,
        live_strat,
    ) -> None:
        """Crash after step 3 (commit complete): recover_scan has no pending rows."""
        _, sid = live_strat
        strat_lean = tmp_path / "strat.lean"

        staging = tmp_path / "staging" / "strat.lean"
        staging.parent.mkdir()
        staging.write_text("-- new proof")

        cw.begin("strategies", "update", row_id=sid)
        cw.stage_file(staging, strat_lean)

        monkeypatch.setenv("COMMIT_FAULT", "after_step3")
        with pytest.raises(CommitFault):
            cw.finalize("strategies", sid, {"status": "succeeded"})
        monkeypatch.delenv("COMMIT_FAULT")

        row = db.execute(
            "SELECT commit_state, status FROM strategies WHERE id=?", (sid,)
        ).fetchone()
        assert row[0] == "live"
        assert row[1] == "succeeded"

        result = cw.recover_scan()
        assert result["strategies"] == []
        row = db.execute(
            "SELECT commit_state FROM strategies WHERE id=?", (sid,)
        ).fetchone()
        assert row[0] == "live"


# ──────────────────────────────────────────────────────────────
# COMMIT_FAULT hook – all 3 modes
# ──────────────────────────────────────────────────────────────


class TestCommitFaultHook:
    def test_fault_after_step1(
        self, db: sqlite3.Connection, cw: CommitWriter, tmp_path, monkeypatch
    ) -> None:
        lean_path = tmp_path / "g.lean"
        monkeypatch.setenv("COMMIT_FAULT", "after_step1")
        with pytest.raises(CommitFault, match="after_step1"):
            cw.begin("goals", "insert", data=_goal_data(str(lean_path)))
        # Row was committed as pending before fault.
        count = db.execute(
            "SELECT COUNT(*) FROM goals WHERE commit_state='pending'"
        ).fetchone()[0]
        assert count == 1

    def test_fault_after_step2(
        self, db: sqlite3.Connection, cw: CommitWriter, tmp_path, monkeypatch
    ) -> None:
        lean_path = tmp_path / "g.lean"
        staging = tmp_path / "s" / "g.lean"
        staging.parent.mkdir()
        staging.write_text("x")

        gid = cw.begin("goals", "insert", data=_goal_data(str(lean_path)))
        monkeypatch.setenv("COMMIT_FAULT", "after_step2")
        with pytest.raises(CommitFault, match="after_step2"):
            cw.stage_file(staging, lean_path)
        # File is at lean_path; row still pending.
        assert lean_path.exists()
        row = db.execute(
            "SELECT commit_state FROM goals WHERE id=?", (gid,)
        ).fetchone()
        assert row[0] == "pending"

    def test_fault_after_step3(
        self, db: sqlite3.Connection, cw: CommitWriter, tmp_path, monkeypatch
    ) -> None:
        lean_path = tmp_path / "g.lean"
        staging = tmp_path / "s" / "g.lean"
        staging.parent.mkdir()
        staging.write_text("x")

        gid = cw.begin("goals", "insert", data=_goal_data(str(lean_path)))
        cw.stage_file(staging, lean_path)
        monkeypatch.setenv("COMMIT_FAULT", "after_step3")
        with pytest.raises(CommitFault, match="after_step3"):
            cw.finalize("goals", gid, {})
        # Row is live (finalize TX committed before fault).
        row = db.execute(
            "SELECT commit_state FROM goals WHERE id=?", (gid,)
        ).fetchone()
        assert row[0] == "live"

    def test_no_fault_without_env(
        self, db: sqlite3.Connection, cw: CommitWriter, tmp_path
    ) -> None:
        lean_path = tmp_path / "g.lean"
        staging = tmp_path / "s" / "g.lean"
        staging.parent.mkdir()
        staging.write_text("x")

        gid = cw.begin("goals", "insert", data=_goal_data(str(lean_path)))
        cw.stage_file(staging, lean_path)
        cw.finalize("goals", gid, {})

        row = db.execute(
            "SELECT commit_state FROM goals WHERE id=?", (gid,)
        ).fetchone()
        assert row[0] == "live"


# ──────────────────────────────────────────────────────────────
# begin_batch – atomicity
# ──────────────────────────────────────────────────────────────


class TestBeginBatch:
    def test_batch_two_inserts_single_tx(
        self, db: sqlite3.Connection, cw: CommitWriter, tmp_path
    ) -> None:
        """Two INSERT ops committed together; both rows are pending afterwards."""
        goal_lean = tmp_path / "goals" / "g.lean"
        goal_lean.parent.mkdir()
        strat_lean = tmp_path / "strat.lean"

        # Need a live goal for strategy FK.
        gid = _insert_live_goal(db, str(goal_lean))

        ids = cw.begin_batch(
            [
                {
                    "table": "goals",
                    "op": "insert",
                    "data": dict(
                        problem="test",
                        slug="batch_g",
                        lean_path=str(tmp_path / "batch_g.lean"),
                        origin="root",
                        kind="theorem",
                        status="open",
                    ),
                },
                {
                    "table": "strategies",
                    "op": "insert",
                    "data": dict(
                        goal_id=gid,
                        lean_path=str(strat_lean),
                        status="proposed",
                    ),
                },
            ]
        )

        assert len(ids) == 2
        for table, rid in zip(("goals", "strategies"), ids):
            row = db.execute(
                f"SELECT commit_state FROM {table} WHERE id=?", (rid,)
            ).fetchone()
            assert row[0] == "pending"

    def test_batch_insert_and_update(
        self, db: sqlite3.Connection, cw: CommitWriter, tmp_path
    ) -> None:
        """INSERT + UPDATE ops in a single batch; both marked pending."""
        goal_lean = tmp_path / "g.lean"
        gid = _insert_live_goal(db, str(goal_lean))

        strat_lean = tmp_path / "strat.lean"
        strat_lean.write_text("-- original")
        sid = _insert_live_strategy(db, gid, str(strat_lean))

        new_goal_lean = tmp_path / "new_g.lean"
        ids = cw.begin_batch(
            [
                {
                    "table": "goals",
                    "op": "insert",
                    "data": dict(
                        problem="test",
                        slug="batch_ng",
                        lean_path=str(new_goal_lean),
                        origin="refuter_negation",
                        kind="theorem",
                        status="open",
                    ),
                },
                {
                    "table": "strategies",
                    "op": "update",
                    "id": sid,
                },
            ]
        )

        assert len(ids) == 2
        new_gid, strat_id = ids
        assert strat_id == sid

        # New goal row pending.
        row = db.execute(
            "SELECT commit_state FROM goals WHERE id=?", (new_gid,)
        ).fetchone()
        assert row[0] == "pending"

        # Strategy row pending with snapshot.
        row = db.execute(
            "SELECT commit_state, prior_state_snapshot FROM strategies WHERE id=?",
            (sid,),
        ).fetchone()
        assert row[0] == "pending"
        assert row[1] is not None

    def test_batch_rolls_back_on_invalid_update_id(
        self, db: sqlite3.Connection, cw: CommitWriter, tmp_path
    ) -> None:
        """If any op fails, the entire batch is rolled back."""
        goal_lean = tmp_path / "g.lean"
        gid = _insert_live_goal(db, str(goal_lean))

        count_before = db.execute("SELECT COUNT(*) FROM goals").fetchone()[0]

        with pytest.raises(ValueError, match="not found"):
            cw.begin_batch(
                [
                    {
                        "table": "goals",
                        "op": "insert",
                        "data": dict(
                            problem="test",
                            slug="rollback_g",
                            lean_path=str(tmp_path / "rb.lean"),
                            origin="root",
                            kind="theorem",
                            status="open",
                        ),
                    },
                    {
                        "table": "strategies",
                        "op": "update",
                        "id": 99999,  # non-existent
                    },
                ]
            )

        # goals table should be unchanged (batch rolled back).
        count_after = db.execute("SELECT COUNT(*) FROM goals").fetchone()[0]
        assert count_after == count_before

    def test_batch_fault_after_step1(
        self, db: sqlite3.Connection, cw: CommitWriter, tmp_path, monkeypatch
    ) -> None:
        """COMMIT_FAULT=after_step1 fires after batch TX commits."""
        goal_lean = tmp_path / "g.lean"
        gid = _insert_live_goal(db, str(goal_lean))

        monkeypatch.setenv("COMMIT_FAULT", "after_step1")
        with pytest.raises(CommitFault):
            cw.begin_batch(
                [
                    {
                        "table": "goals",
                        "op": "insert",
                        "data": dict(
                            problem="test",
                            slug="fault_g",
                            lean_path=str(tmp_path / "f.lean"),
                            origin="root",
                            kind="theorem",
                            status="open",
                        ),
                    }
                ]
            )

        # Batch TX committed before fault: row is pending.
        count = db.execute(
            "SELECT COUNT(*) FROM goals WHERE commit_state='pending'"
        ).fetchone()[0]
        assert count == 1


# ──────────────────────────────────────────────────────────────
# begin_batch – junction tables (strategy_subgoals)
# ──────────────────────────────────────────────────────────────


class TestBeginBatchJunction:
    """begin_batch supports junction-table inserts via junction_ops_factory."""

    def test_junction_factory_inserts_in_same_tx(
        self, db: sqlite3.Connection, cw: CommitWriter, tmp_path
    ) -> None:
        goal_lean = tmp_path / "g.lean"
        goal_lean.parent.mkdir(parents=True, exist_ok=True)
        gid = _insert_live_goal(db, str(goal_lean))

        strat_lean = tmp_path / "strat.lean"
        sub_g_lean = tmp_path / "sub_g.lean"

        def make_junction(ids: list[int]) -> list[dict]:
            strat_id, sub_g_id = ids
            return [{
                "table": "strategy_subgoals",
                "op": "insert",
                "data": {
                    "strategy_id": strat_id,
                    "subgoal_id": sub_g_id,
                    "position": 0,
                },
            }]

        ids = cw.begin_batch(
            [
                {
                    "table": "strategies",
                    "op": "insert",
                    "data": dict(
                        goal_id=gid,
                        lean_path=str(strat_lean),
                        status="proposed",
                    ),
                },
                {
                    "table": "goals",
                    "op": "insert",
                    "data": dict(
                        problem="test",
                        slug="sub_g",
                        lean_path=str(sub_g_lean),
                        origin="backward",
                        kind="theorem",
                        status="open",
                    ),
                },
            ],
            junction_ops_factory=make_junction,
        )
        strat_id, sub_g_id = ids

        # Both main rows pending.
        assert db.execute(
            "SELECT commit_state FROM strategies WHERE id=?", (strat_id,)
        ).fetchone()[0] == "pending"
        assert db.execute(
            "SELECT commit_state FROM goals WHERE id=?", (sub_g_id,)
        ).fetchone()[0] == "pending"

        # Junction row exists with correct linkage.
        row = db.execute(
            "SELECT strategy_id, subgoal_id, position FROM strategy_subgoals "
            "WHERE strategy_id=?",
            (strat_id,),
        ).fetchone()
        assert row == (strat_id, sub_g_id, 0)

    def test_junction_table_in_main_ops_raises(
        self, db: sqlite3.Connection, cw: CommitWriter, tmp_path
    ) -> None:
        with pytest.raises(ValueError, match="junction table"):
            cw.begin_batch([
                {
                    "table": "strategy_subgoals",
                    "op": "insert",
                    "data": {"strategy_id": 1, "subgoal_id": 1, "position": 0},
                },
            ])

    def test_junction_factory_non_junction_table_raises(
        self, db: sqlite3.Connection, cw: CommitWriter, tmp_path
    ) -> None:
        goal_lean = tmp_path / "g.lean"
        gid = _insert_live_goal(db, str(goal_lean))

        def bad_factory(ids: list[int]) -> list[dict]:
            return [{
                "table": "goals",  # not a junction table
                "op": "insert",
                "data": _goal_data(str(tmp_path / "x.lean")),
            }]

        with pytest.raises(ValueError, match="non-junction"):
            cw.begin_batch(
                [
                    {
                        "table": "goals",
                        "op": "insert",
                        "data": dict(
                            problem="test",
                            slug="x",
                            lean_path=str(tmp_path / "y.lean"),
                            origin="root",
                            kind="theorem",
                            status="open",
                        ),
                    },
                ],
                junction_ops_factory=bad_factory,
            )

        # Main op also rolled back.
        count = db.execute(
            "SELECT COUNT(*) FROM goals WHERE slug='x'"
        ).fetchone()[0]
        assert count == 0

    def test_junction_factory_non_insert_op_raises(
        self, db: sqlite3.Connection, cw: CommitWriter, tmp_path
    ) -> None:
        goal_lean = tmp_path / "g.lean"
        gid = _insert_live_goal(db, str(goal_lean))

        def bad_factory(ids: list[int]) -> list[dict]:
            return [{
                "table": "strategy_subgoals",
                "op": "update",  # only insert allowed
                "data": {},
            }]

        with pytest.raises(ValueError, match="must be 'insert'"):
            cw.begin_batch(
                [
                    {
                        "table": "strategies",
                        "op": "insert",
                        "data": dict(
                            goal_id=gid,
                            lean_path=str(tmp_path / "s.lean"),
                            status="proposed",
                        ),
                    },
                ],
                junction_ops_factory=bad_factory,
            )

    def test_junction_atomicity_main_op_fails(
        self, db: sqlite3.Connection, cw: CommitWriter, tmp_path
    ) -> None:
        """If a main op fails (e.g. UPDATE with bad id), junction ops must not
        leak into DB."""
        goal_lean = tmp_path / "g.lean"
        gid = _insert_live_goal(db, str(goal_lean))

        def make_junction(ids: list[int]) -> list[dict]:
            return [{
                "table": "strategy_subgoals",
                "op": "insert",
                "data": {"strategy_id": ids[0], "subgoal_id": gid, "position": 0},
            }]

        with pytest.raises(ValueError, match="not found"):
            cw.begin_batch(
                [
                    {
                        "table": "strategies",
                        "op": "insert",
                        "data": dict(
                            goal_id=gid,
                            lean_path=str(tmp_path / "s.lean"),
                            status="proposed",
                        ),
                    },
                    {
                        "table": "strategies",
                        "op": "update",
                        "id": 99999,  # non-existent
                    },
                ],
                junction_ops_factory=make_junction,
            )

        # Both main and junction should be rolled back.
        assert db.execute(
            "SELECT COUNT(*) FROM strategies WHERE lean_path LIKE '%s.lean'"
        ).fetchone()[0] == 0
        assert db.execute(
            "SELECT COUNT(*) FROM strategy_subgoals"
        ).fetchone()[0] == 0


# ──────────────────────────────────────────────────────────────
# recover_scan – cascade cleanup of strategy_subgoals
# ──────────────────────────────────────────────────────────────


class TestRecoverCascade:
    """recover_scan must cascade-delete junction rows when a pending strategy
    or goal is rolled back, otherwise FK constraints crash on parent DELETE."""

    def test_pending_strategy_delete_cascades_junction(
        self, db: sqlite3.Connection, cw: CommitWriter, tmp_path
    ) -> None:
        # Setup: pending strategy + pending goal, junction linking them, no files.
        goal_lean = tmp_path / "g.lean"
        gid = _insert_live_goal(db, str(goal_lean))

        strat_lean = tmp_path / "strat.lean"  # NOT on disk
        sub_g_lean = tmp_path / "sub_g.lean"  # NOT on disk

        def make_junction(ids: list[int]) -> list[dict]:
            return [{
                "table": "strategy_subgoals",
                "op": "insert",
                "data": {
                    "strategy_id": ids[0],
                    "subgoal_id": ids[1],
                    "position": 0,
                },
            }]

        ids = cw.begin_batch(
            [
                {
                    "table": "strategies",
                    "op": "insert",
                    "data": dict(
                        goal_id=gid,
                        lean_path=str(strat_lean),
                        status="proposed",
                    ),
                },
                {
                    "table": "goals",
                    "op": "insert",
                    "data": dict(
                        problem="test",
                        slug="sub_g",
                        lean_path=str(sub_g_lean),
                        origin="backward",
                        kind="theorem",
                        status="open",
                    ),
                },
            ],
            junction_ops_factory=make_junction,
        )
        strat_id, sub_g_id = ids

        # Sanity: junction row exists, files don't exist.
        assert db.execute(
            "SELECT COUNT(*) FROM strategy_subgoals"
        ).fetchone()[0] == 1
        assert not strat_lean.exists()
        assert not sub_g_lean.exists()

        # recover_scan should DELETE strategy + sub-goal + junction without FK error.
        result = cw.recover_scan()

        # All rows cleaned up; live goal pre-existing remains.
        assert db.execute(
            "SELECT COUNT(*) FROM strategies WHERE id=?", (strat_id,)
        ).fetchone()[0] == 0
        assert db.execute(
            "SELECT COUNT(*) FROM goals WHERE id=?", (sub_g_id,)
        ).fetchone()[0] == 0
        assert db.execute(
            "SELECT COUNT(*) FROM strategy_subgoals"
        ).fetchone()[0] == 0
        # Pre-existing live goal untouched.
        assert db.execute(
            "SELECT commit_state FROM goals WHERE id=?", (gid,)
        ).fetchone()[0] == "live"
        assert strat_id in result["strategies"]
        assert sub_g_id in result["goals"]

    def test_pending_strategy_with_partial_files_consistent(
        self, db: sqlite3.Connection, cw: CommitWriter, tmp_path
    ) -> None:
        """COMMIT_FAULT=after_step2 mid-flow simulation: strategy file moved,
        sub-goal file not. recover_scan finalizes strategy and DELETEs sub-goal,
        cascading the junction row tied to that sub-goal — no FK error."""
        goal_lean = tmp_path / "g.lean"
        gid = _insert_live_goal(db, str(goal_lean))

        strat_lean = tmp_path / "strat.lean"
        strat_lean.write_text("-- strategy stub")  # exists
        sub_g_lean = tmp_path / "sub_g.lean"  # NOT on disk

        def make_junction(ids: list[int]) -> list[dict]:
            return [{
                "table": "strategy_subgoals",
                "op": "insert",
                "data": {
                    "strategy_id": ids[0],
                    "subgoal_id": ids[1],
                    "position": 0,
                },
            }]

        ids = cw.begin_batch(
            [
                {
                    "table": "strategies",
                    "op": "insert",
                    "data": dict(
                        goal_id=gid,
                        lean_path=str(strat_lean),
                        status="proposed",
                    ),
                },
                {
                    "table": "goals",
                    "op": "insert",
                    "data": dict(
                        problem="test",
                        slug="sub_g",
                        lean_path=str(sub_g_lean),
                        origin="backward",
                        kind="theorem",
                        status="open",
                    ),
                },
            ],
            junction_ops_factory=make_junction,
        )
        strat_id, sub_g_id = ids

        cw.recover_scan()

        # Strategy: file exists → finalize live.
        assert db.execute(
            "SELECT commit_state FROM strategies WHERE id=?", (strat_id,)
        ).fetchone()[0] == "live"
        # Sub-goal: file missing → DELETE'd.
        assert db.execute(
            "SELECT COUNT(*) FROM goals WHERE id=?", (sub_g_id,)
        ).fetchone()[0] == 0
        # Junction row referencing the dropped sub-goal cascaded.
        assert db.execute(
            "SELECT COUNT(*) FROM strategy_subgoals "
            "WHERE subgoal_id=?",
            (sub_g_id,),
        ).fetchone()[0] == 0


# ──────────────────────────────────────────────────────────────
# stage_file idempotence
# ──────────────────────────────────────────────────────────────


class TestStageFile:
    def test_idempotent_same_content(
        self, cw: CommitWriter, tmp_path
    ) -> None:
        src = tmp_path / "src.lean"
        dst = tmp_path / "dst.lean"
        src.write_bytes(b"content")
        dst.write_bytes(b"content")  # same content already at dst

        cw.stage_file(src, dst)  # should not raise or overwrite
        assert dst.read_bytes() == b"content"

    def test_moves_file_when_dst_absent(
        self, cw: CommitWriter, tmp_path
    ) -> None:
        src = tmp_path / "src.lean"
        dst = tmp_path / "sub" / "dst.lean"
        src.write_bytes(b"hello")

        cw.stage_file(src, dst)

        assert dst.exists()
        assert dst.read_bytes() == b"hello"
        assert not src.exists()

    def test_skips_when_src_gone_dst_present(
        self, cw: CommitWriter, tmp_path
    ) -> None:
        dst = tmp_path / "dst.lean"
        dst.write_bytes(b"already here")
        # src does not exist – move already happened.
        src = tmp_path / "nonexistent.lean"

        cw.stage_file(src, dst)  # should be a no-op, not raise
        assert dst.read_bytes() == b"already here"

    def test_overwrites_when_dst_exists_diff_hash(
        self, cw: CommitWriter, tmp_path
    ) -> None:
        """Both src and dst exist with different content → overwrite dst with src.
        shutil.move on existing dst maps to os.replace (atomic overwrite).
        """
        src = tmp_path / "src.lean"
        src.write_bytes(b"new content")
        dst = tmp_path / "dst.lean"
        dst.write_bytes(b"old content")

        cw.stage_file(src, dst)

        assert dst.read_bytes() == b"new content"
        assert not src.exists()
