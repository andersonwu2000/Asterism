"""Tests for Tooling/db/schema_v1.sql.

Validates:
  1. All 13 tables are created (schema can be applied).
  2. Column counts match architecture v3 §9.1.
  3. Critical NOT NULL / UNIQUE / PK / CHECK constraints are enforced.
"""
from __future__ import annotations

import sqlite3
import pytest

from Tooling.db.connect import connect, init_schema


# ──────────────────────────────────────────────────────────────
# Fixture: in-memory DB with schema applied
# ──────────────────────────────────────────────────────────────

@pytest.fixture
def db() -> sqlite3.Connection:
    conn = connect(":memory:")
    init_schema(conn)
    yield conn
    conn.close()


def _columns(conn: sqlite3.Connection, table: str) -> list[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return [r[1] for r in rows]


def _col_count(conn: sqlite3.Connection, table: str) -> int:
    return len(_columns(conn, table))


# ──────────────────────────────────────────────────────────────
# 1. All 13 tables present
# ──────────────────────────────────────────────────────────────

ALL_TABLES = [
    "goals",
    "strategies",
    "strategy_subgoals",
    "pipelines",
    "dead_attempts",
    "queue",
    "events",
    "schedulers",
    "continuous_tasks",
    "construction_attempts",
    "library_index",
    "search_cache",
    "strategist_decisions",
]


def test_all_tables_exist(db):
    rows = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    existing = {r[0] for r in rows}
    for t in ALL_TABLES:
        assert t in existing, f"Missing table: {t}"


# ──────────────────────────────────────────────────────────────
# 2. Column counts per table (spec §9.1)
# ──────────────────────────────────────────────────────────────

EXPECTED_COLUMN_COUNTS = {
    "goals":                  21,
    "strategies":              9,
    "strategy_subgoals":       3,
    "pipelines":              10,
    "dead_attempts":           8,
    "queue":                   6,
    "events":                  4,
    "schedulers":              5,
    "continuous_tasks":        8,
    "construction_attempts":   7,
    "library_index":           5,
    "search_cache":            5,
    "strategist_decisions":    3,
}


@pytest.mark.parametrize("table,expected", list(EXPECTED_COLUMN_COUNTS.items()))
def test_column_count(db, table, expected):
    actual = _col_count(db, table)
    assert actual == expected, (
        f"{table}: expected {expected} columns, got {actual}. "
        f"Columns: {_columns(db, table)}"
    )


# ──────────────────────────────────────────────────────────────
# 3. NOT NULL constraints
# ──────────────────────────────────────────────────────────────

NOW = "2026-01-01T00:00:00"

PIPELINE_ID = "aaaaaaaa-0000-0000-0000-000000000000"


def _insert_pipeline(db: sqlite3.Connection, pid: str = PIPELINE_ID) -> None:
    db.execute(
        "INSERT INTO pipelines(id,kind,runtime,target_id,target_kind,status,started_at)"
        " VALUES(?,?,?,?,?,?,?)",
        (pid, "Builder", "atomic", "G1", "Goal", "running", NOW),
    )


def _insert_goal(db: sqlite3.Connection, gid: int = 1) -> None:
    db.execute(
        "INSERT INTO goals(id,problem,slug,lean_path,origin,kind,status,commit_state,created_at,updated_at)"
        " VALUES(?,?,?,?,?,?,?,?,?,?)",
        (gid, "ex", f"sl{gid}", f"path_{gid}.lean",
         "root", "theorem", "open", "live", NOW, NOW),
    )


class TestNotNull:
    def test_goals_problem_required(self, db):
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "INSERT INTO goals(slug,lean_path,origin,kind,status,commit_state,created_at,updated_at)"
                " VALUES(?,?,?,?,?,?,?,?)",
                ("s", "lp.lean", "root", "theorem", "open", "live", NOW, NOW),
            )

    def test_goals_lean_path_required(self, db):
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "INSERT INTO goals(problem,slug,origin,kind,status,commit_state,created_at,updated_at)"
                " VALUES(?,?,?,?,?,?,?,?)",
                ("ex", "s", "root", "theorem", "open", "live", NOW, NOW),
            )

    def test_goals_status_required(self, db):
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "INSERT INTO goals(problem,slug,lean_path,origin,kind,commit_state,created_at,updated_at)"
                " VALUES(?,?,?,?,?,?,?,?)",
                ("ex", "s", "lp.lean", "root", "theorem", "live", NOW, NOW),
            )

    def test_goals_commit_state_required(self, db):
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "INSERT INTO goals(problem,slug,lean_path,origin,kind,status,created_at,updated_at)"
                " VALUES(?,?,?,?,?,?,?,?)",
                ("ex", "s", "lp.lean", "root", "theorem", "open", NOW, NOW),
            )

    def test_strategies_goal_id_required(self, db):
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "INSERT INTO strategies(lean_path,status,commit_state,created_at)"
                " VALUES(?,?,?,?)",
                ("s.lean", "proposed", "live", NOW),
            )

    def test_strategies_lean_path_required(self, db):
        _insert_goal(db)
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "INSERT INTO strategies(goal_id,status,commit_state,created_at)"
                " VALUES(?,?,?,?)",
                (1, "proposed", "live", NOW),
            )

    def test_dead_attempts_pipeline_id_required(self, db):
        # Spec §9.1: dead_attempts.pipeline_id has no nullable marker; every
        # row originates from some pipeline run, so NULL is a real schema bug.
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "INSERT INTO dead_attempts(target_id,target_kind,pipeline_kind,outcome,reason_summary,ts)"
                " VALUES(?,?,?,?,?,?)",
                ("G1", "Goal", "Builder", "exhausted", "no pipeline_id", NOW),
            )


# ──────────────────────────────────────────────────────────────
# 4. UNIQUE constraints
# ──────────────────────────────────────────────────────────────

class TestUnique:
    def test_goals_lean_path_unique(self, db):
        db.execute(
            "INSERT INTO goals(problem,slug,lean_path,origin,kind,status,commit_state,created_at,updated_at)"
            " VALUES(?,?,?,?,?,?,?,?,?)",
            ("ex", "s1", "same.lean", "root", "theorem", "open", "live", NOW, NOW),
        )
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "INSERT INTO goals(problem,slug,lean_path,origin,kind,status,commit_state,created_at,updated_at)"
                " VALUES(?,?,?,?,?,?,?,?,?)",
                ("ex", "s2", "same.lean", "root", "theorem", "open", "live", NOW, NOW),
            )

    def test_strategies_lean_path_unique(self, db):
        _insert_goal(db)
        db.execute(
            "INSERT INTO strategies(goal_id,lean_path,status,commit_state,created_at)"
            " VALUES(?,?,?,?,?)",
            (1, "strat.lean", "proposed", "live", NOW),
        )
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "INSERT INTO strategies(goal_id,lean_path,status,commit_state,created_at)"
                " VALUES(?,?,?,?,?)",
                (1, "strat.lean", "proposed", "live", NOW),
            )


# ──────────────────────────────────────────────────────────────
# 5. Composite PKs
# ──────────────────────────────────────────────────────────────

class TestCompositePK:
    def test_strategy_subgoals_composite_pk(self, db):
        _insert_goal(db, 1)
        _insert_goal(db, 2)
        db.execute(
            "INSERT INTO strategies(id,goal_id,lean_path,status,commit_state,created_at)"
            " VALUES(?,?,?,?,?,?)",
            (1, 1, "st.lean", "proposed", "live", NOW),
        )
        db.execute(
            "INSERT INTO strategy_subgoals(strategy_id,subgoal_id,position) VALUES(?,?,?)",
            (1, 2, 0),
        )
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "INSERT INTO strategy_subgoals(strategy_id,subgoal_id,position) VALUES(?,?,?)",
                (1, 2, 1),
            )

    def test_strategy_subgoals_position_unique_per_strategy(self, db):
        # AND-group ordering: two distinct subgoals under one strategy may not
        # share the same position. Composite PK alone (strategy_id, subgoal_id)
        # does not enforce this; UNIQUE(strategy_id, position) does.
        _insert_goal(db, 1)
        _insert_goal(db, 2)
        _insert_goal(db, 3)
        db.execute(
            "INSERT INTO strategies(id,goal_id,lean_path,status,commit_state,created_at)"
            " VALUES(?,?,?,?,?,?)",
            (1, 1, "st.lean", "proposed", "live", NOW),
        )
        db.execute(
            "INSERT INTO strategy_subgoals(strategy_id,subgoal_id,position) VALUES(?,?,?)",
            (1, 2, 0),
        )
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "INSERT INTO strategy_subgoals(strategy_id,subgoal_id,position) VALUES(?,?,?)",
                (1, 3, 0),
            )

    def test_library_index_composite_pk(self, db):
        _insert_goal(db)
        db.execute(
            "INSERT INTO library_index(layer,name,path,source_root_id,committed_at)"
            " VALUES(?,?,?,?,?)",
            ("Theorems", "ex.add_zero", "Library/Theorems/proved.lean", 1, NOW),
        )
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "INSERT INTO library_index(layer,name,path,source_root_id,committed_at)"
                " VALUES(?,?,?,?,?)",
                ("Theorems", "ex.add_zero", "other.lean", 1, NOW),
            )


# ──────────────────────────────────────────────────────────────
# 6. CHECK constraints (enums)
# ──────────────────────────────────────────────────────────────

class TestCheckConstraints:
    def test_goals_origin_enum(self, db):
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "INSERT INTO goals(problem,slug,lean_path,origin,kind,status,commit_state,created_at,updated_at)"
                " VALUES(?,?,?,?,?,?,?,?,?)",
                ("ex", "s", "lp.lean", "invalid_origin", "theorem", "open", "live", NOW, NOW),
            )

    def test_goals_kind_enum(self, db):
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "INSERT INTO goals(problem,slug,lean_path,origin,kind,status,commit_state,created_at,updated_at)"
                " VALUES(?,?,?,?,?,?,?,?,?)",
                ("ex", "s", "lp.lean", "root", "bad_kind", "open", "live", NOW, NOW),
            )

    def test_goals_status_enum(self, db):
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "INSERT INTO goals(problem,slug,lean_path,origin,kind,status,commit_state,created_at,updated_at)"
                " VALUES(?,?,?,?,?,?,?,?,?)",
                ("ex", "s", "lp.lean", "root", "theorem", "bad_status", "live", NOW, NOW),
            )

    def test_goals_commit_state_enum(self, db):
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "INSERT INTO goals(problem,slug,lean_path,origin,kind,status,commit_state,created_at,updated_at)"
                " VALUES(?,?,?,?,?,?,?,?,?)",
                ("ex", "s", "lp.lean", "root", "theorem", "open", "bad_state", NOW, NOW),
            )

    def test_pipelines_kind_enum(self, db):
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "INSERT INTO pipelines(id,kind,runtime,target_id,target_kind,status,started_at)"
                " VALUES(?,?,?,?,?,?,?)",
                ("uuid1", "BadKind", "atomic", "G1", "Goal", "running", NOW),
            )

    def test_events_kind_enum(self, db):
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "INSERT INTO events(kind,ts) VALUES(?,?)",
                ("bad_event", NOW),
            )

    def test_queue_kind_enum(self, db):
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "INSERT INTO queue(kind,target_id,priority,created_at) VALUES(?,?,?,?)",
                ("bad_kind", "G1", 0, NOW),
            )


# ──────────────────────────────────────────────────────────────
# 7. Valid full-row inserts (smoke test all tables)
# ──────────────────────────────────────────────────────────────

class TestValidInserts:
    def test_insert_goal(self, db):
        _insert_goal(db)
        row = db.execute("SELECT id,status FROM goals WHERE id=1").fetchone()
        assert row == (1, "open")

    def test_insert_pipeline(self, db):
        _insert_pipeline(db)
        row = db.execute("SELECT id,kind FROM pipelines WHERE id=?",
                         (PIPELINE_ID,)).fetchone()
        assert row[1] == "Builder"

    def test_insert_dead_attempt(self, db):
        _insert_pipeline(db)
        db.execute(
            "INSERT INTO dead_attempts(target_id,target_kind,pipeline_id,pipeline_kind,outcome,reason_summary,ts)"
            " VALUES(?,?,?,?,?,?,?)",
            ("G1", "Goal", PIPELINE_ID, "Builder", "exhausted", "all tactics failed", NOW),
        )
        count = db.execute("SELECT COUNT(*) FROM dead_attempts").fetchone()[0]
        assert count == 1

    def test_insert_queue_row(self, db):
        db.execute(
            "INSERT INTO queue(kind,target_id,priority,created_at) VALUES(?,?,?,?)",
            ("Builder", "S1", 0, NOW),
        )
        row = db.execute("SELECT kind,priority FROM queue").fetchone()
        assert row == ("Builder", 0)

    def test_insert_event(self, db):
        db.execute(
            "INSERT INTO events(kind,payload,ts) VALUES(?,?,?)",
            ("pipeline_finished", '{"pipeline_id":"x"}', NOW),
        )
        row = db.execute("SELECT kind FROM events").fetchone()
        assert row[0] == "pipeline_finished"

    def test_insert_search_cache(self, db):
        db.execute(
            "INSERT INTO search_cache(query_hash,scope,mode,results,expires_at)"
            " VALUES(?,?,?,?,?)",
            ("hash1", "mathlib", "find", "[]", NOW),
        )

    def test_insert_strategist_decisions(self, db):
        db.execute(
            "INSERT INTO strategist_decisions(decisions,ts) VALUES(?,?)",
            ('[]', NOW),
        )

    def test_insert_scheduler(self, db):
        db.execute(
            "INSERT INTO schedulers(host,pid,started_at,last_heartbeat)"
            " VALUES(?,?,?,?)",
            ("localhost", 1234, NOW, NOW),
        )

    def test_insert_continuous_task(self, db):
        # P5+ schema; smoke insert ensures column names did not drift.
        _insert_pipeline(db)
        db.execute(
            "INSERT INTO continuous_tasks(pipeline_id,checkpoint_state,last_checkpoint_at,"
            "budget_tokens,budget_wall_clock_sec,consumed_tokens,consumed_wall_clock_sec,lifecycle_state)"
            " VALUES(?,?,?,?,?,?,?,?)",
            (PIPELINE_ID, '{"generation":0}', NOW, 100000, 14400, 0, 0, "running"),
        )
        row = db.execute(
            "SELECT lifecycle_state,consumed_tokens FROM continuous_tasks WHERE pipeline_id=?",
            (PIPELINE_ID,),
        ).fetchone()
        assert row == ("running", 0)

    def test_insert_construction_attempt(self, db):
        # P5+ schema; smoke insert ensures column names did not drift.
        _insert_pipeline(db)
        db.execute(
            "INSERT INTO construction_attempts(pipeline_id,generation,parent_attempt_id,"
            "candidate_lean_path,score,created_at)"
            " VALUES(?,?,?,?,?,?)",
            (PIPELINE_ID, 1, None, "Tasks/abc/candidates/c1.lean", 0.42, NOW),
        )
        row = db.execute(
            "SELECT generation,score FROM construction_attempts WHERE pipeline_id=?",
            (PIPELINE_ID,),
        ).fetchone()
        assert row == (1, 0.42)

    def test_insert_library_index(self, db):
        # P6+ schema; smoke insert ensures column names did not drift.
        _insert_goal(db)
        db.execute(
            "INSERT INTO library_index(layer,name,path,source_root_id,committed_at)"
            " VALUES(?,?,?,?,?)",
            ("Theorems", "ex.add_zero", "Library/Theorems/proved.lean", 1, NOW),
        )
        row = db.execute(
            "SELECT layer,name FROM library_index"
        ).fetchone()
        assert row == ("Theorems", "ex.add_zero")
