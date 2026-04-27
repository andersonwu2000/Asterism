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

    def test_update_after_step1_restores_row(
        self,
        db: sqlite3.Connection,
        cw: CommitWriter,
        tmp_path,
        monkeypatch,
        live_strat,
    ) -> None:
        """Crash after step 1 (pending + snapshot, file not moved): restore original."""
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
