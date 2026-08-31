"""v38 — pipelines rows exist for the whole pipeline lifetime.

The pipelines row is INSERTed status='running' at dispatch
(`db.record_pipeline_start`) and UPDATEd at completion
(`db.finish_pipeline`), so the `dead_attempts.pipeline_id` FK target
exists while the pipeline runs and forensic rows can be written eagerly,
1:1 with each `goals.attempts` increment (the goal-7486 drift class,
2026-08-08).

Pins:
  * fresh DB (`init_schema`) and a v37-shaped DB migrated forward
    converge on the SAME pipelines shape (table_info + status CHECK)
    and the same user_version — both directions
  * the migration preserves rows + the dead_attempts FK and is
    idempotent
  * `finish_pipeline` without a prior start fails LOUD (a finish
    without a dispatch-time INSERT is a dispatch bug)
  * startup recovery finalizes stale 'running' rows as
    failed / outcome='daemon_crashed', scope-filtered, and spares rows
    whose .attempts/<pid>/ sandbox manifest names a live owner (#90
    concurrent-driver class)
"""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

import pytest

from Tooling.state import db, db_migrations, recovery


# The pipelines DDL exactly as a v37 DB carried it (status CHECK without
# 'running'; outcome / finished_at NOT NULL).
_V37_PIPELINES_DDL = """
CREATE TABLE pipelines (
    id          TEXT PRIMARY KEY,
    kind        TEXT NOT NULL
                    CHECK(kind IN ('Builder','Backward','Verify',
                                   'Strategist','Forward','Librarian',
                                   'Scholar','Formalizer')),
    target_id   TEXT NOT NULL,
    target_kind TEXT NOT NULL
                    CHECK(target_kind IN ('Goal','Strategy','Problem',
                                          'Group')),
    status      TEXT NOT NULL CHECK(status IN ('succeeded','failed')),
    outcome     TEXT NOT NULL,
    started_at  TEXT NOT NULL,
    finished_at TEXT NOT NULL
)"""


def _fresh(tmp_path: Path, name: str) -> sqlite3.Connection:
    conn = sqlite3.connect(str(tmp_path / name), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    db.init_schema(conn)
    return conn


def _table_info(conn: sqlite3.Connection) -> list:
    """(name, type, notnull, dflt, pk) per column — the shape a reader
    actually depends on, robust to DDL whitespace."""
    return [(r[1], r[2], r[3], r[4], r[5])
            for r in conn.execute("PRAGMA table_info(pipelines)")]


def _ddl(conn: sqlite3.Connection) -> str:
    return conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table'"
        " AND name='pipelines'").fetchone()[0]


def _rewind_pipelines_to_v37(conn: sqlite3.Connection) -> None:
    """Rebuild `pipelines` back to its pre-v38 shape and stamp v37, so
    `db_migrations.apply` exercises the real forward step."""
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.executescript(
        "DROP TABLE pipelines;\n" + _V37_PIPELINES_DDL + ";\n"
        "CREATE INDEX IF NOT EXISTS idx_pipelines_status"
        " ON pipelines(status);\n")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA user_version = 37")
    conn.commit()


def _seed_problem_goal(conn: sqlite3.Connection, problem: str) -> int:
    conn.execute(
        "INSERT INTO problems (name, created_at,"
        " bootstrap_done) VALUES (?, ?, 1)",
        (problem, db.now()))
    conn.commit()
    return db.insert_goal(
        conn, problem=problem, slug="g",
        lean_path=f"Problems/{problem}/Root.lean",
        statement="True", origin="root")


# ---------------------------------------------------------------------
# Schema shape — fresh vs migrated
# ---------------------------------------------------------------------

def test_fresh_db_pipelines_shape(tmp_path: Path) -> None:
    conn = _fresh(tmp_path, "fresh.db")
    assert (conn.execute("PRAGMA user_version").fetchone()[0]
            == db._CURRENT_USER_VERSION == 47)
    ddl = _ddl(conn)
    assert "'running'" in ddl
    # outcome / finished_at are NULLable (a running row has neither).
    notnull = {r[1]: r[3] for r in conn.execute(
        "PRAGMA table_info(pipelines)")}
    assert notnull["outcome"] == 0
    assert notnull["finished_at"] == 0
    assert notnull["status"] == 1 and notnull["started_at"] == 1
    # 'running' is admitted; garbage is not.
    db.record_pipeline_start(conn, pipeline_id="pf-1", kind="Formalizer",
                             target_id="1", target_kind="Goal")
    row = conn.execute("SELECT * FROM pipelines WHERE id='pf-1'").fetchone()
    assert row["status"] == "running"
    assert row["outcome"] is None and row["finished_at"] is None
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO pipelines (id, kind, target_id, target_kind,"
            " status, outcome, started_at, finished_at)"
            " VALUES ('bad', 'Formalizer', '1', 'Goal', 'zombie', NULL,"
            " ?, NULL)", (db.now(),))
    conn.close()


def test_v37_db_migrates_to_same_shape_as_fresh(tmp_path: Path) -> None:
    """Both directions of the completion condition: an OLD DB migrated
    forward and a fresh `init_schema` DB end at the same user_version
    and the same pipelines shape — with the old rows and their
    dead_attempts FK intact."""
    fresh = _fresh(tmp_path, "fresh.db")

    old = _fresh(tmp_path, "old.db")
    _rewind_pipelines_to_v37(old)
    # A finished v37-era row + a dead_attempts row FK'd to it.
    old.execute(
        "INSERT INTO pipelines (id, kind, target_id, target_kind, status,"
        " outcome, started_at, finished_at)"
        " VALUES ('old-1', 'Backward', '7', 'Goal', 'failed', 'exhausted',"
        " ?, ?)", (db.now(), db.now()))
    old.execute(
        "INSERT INTO dead_attempts (target_id, target_kind, pipeline_id,"
        " failure_reason, ts) VALUES (7, 'Goal', 'old-1',"
        " 'lake_build_error', ?)", (db.now(),))
    old.commit()
    assert "'running'" not in _ddl(old)

    db_migrations.apply(old)

    assert (old.execute("PRAGMA user_version").fetchone()[0]
            == fresh.execute("PRAGMA user_version").fetchone()[0] == 47)
    assert _table_info(old) == _table_info(fresh)
    assert "'running'" in _ddl(old)
    # Row + FK survived the rebuild.
    r = old.execute("SELECT * FROM pipelines WHERE id='old-1'").fetchone()
    assert (r["status"], r["outcome"]) == ("failed", "exhausted")
    assert old.execute(
        "SELECT COUNT(*) FROM dead_attempts WHERE pipeline_id='old-1'"
    ).fetchone()[0] == 1
    assert list(old.execute("PRAGMA foreign_key_check")) == []
    # The widened CHECK now admits 'running' on the migrated DB too.
    db.record_pipeline_start(old, pipeline_id="new-1", kind="Formalizer",
                             target_id="7", target_kind="Goal")
    # The status index survived the rebuild.
    assert old.execute(
        "SELECT 1 FROM sqlite_master WHERE type='index'"
        " AND name='idx_pipelines_status'").fetchone() is not None
    fresh.close()
    old.close()


def test_v38_migration_idempotent(tmp_path: Path) -> None:
    conn = _fresh(tmp_path, "idem.db")
    _rewind_pipelines_to_v37(conn)
    db_migrations.apply(conn)
    ddl_once = _ddl(conn)
    db_migrations.apply(conn)          # second run must be a no-op
    assert _ddl(conn) == ddl_once
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 47
    conn.close()


def test_connect_auto_migrates_v37_file(tmp_path: Path) -> None:
    """`db.connect` on an on-disk DB whose user_version trails must run
    the migration (the daemon-start path for a pre-v38 asterism.db)."""
    path = tmp_path / "old_disk.db"
    conn = sqlite3.connect(str(path), timeout=30)
    conn.row_factory = sqlite3.Row
    db.init_schema(conn)
    _rewind_pipelines_to_v37(conn)
    conn.close()

    c2 = db.connect(path)
    assert c2.execute("PRAGMA user_version").fetchone()[0] == 47
    assert "'running'" in _ddl(c2)
    c2.close()


# ---------------------------------------------------------------------
# start / finish lifecycle
# ---------------------------------------------------------------------

def test_finish_pipeline_updates_the_running_row(tmp_path: Path) -> None:
    conn = _fresh(tmp_path, "life.db")
    db.record_pipeline_start(conn, pipeline_id="pl-1", kind="Strategist",
                             target_id="3", target_kind="Group")
    db.finish_pipeline(conn, pipeline_id="pl-1", status="succeeded",
                       outcome="success")
    r = conn.execute("SELECT * FROM pipelines WHERE id='pl-1'").fetchone()
    assert (r["status"], r["outcome"]) == ("succeeded", "success")
    assert r["finished_at"] is not None
    # Exactly one row — finish UPDATEs, never INSERTs a second.
    assert conn.execute(
        "SELECT COUNT(*) FROM pipelines").fetchone()[0] == 1
    conn.close()


def test_finish_pipeline_without_start_raises(tmp_path: Path) -> None:
    conn = _fresh(tmp_path, "orphanfinish.db")
    with pytest.raises(RuntimeError, match="record_pipeline_start"):
        db.finish_pipeline(conn, pipeline_id="ghost", status="failed",
                           outcome="failed")
    conn.close()


# ---------------------------------------------------------------------
# startup recovery of stale 'running' rows
# ---------------------------------------------------------------------

def test_recovery_finalizes_running_rows_scope_filtered(
        tmp_path: Path) -> None:
    conn = _fresh(tmp_path, "rec.db")
    g1 = _seed_problem_goal(conn, "p_one")
    g2 = _seed_problem_goal(conn, "p_two")
    db.record_pipeline_start(conn, pipeline_id="run-1", kind="Formalizer",
                             target_id=str(g1), target_kind="Goal")
    db.record_pipeline_start(conn, pipeline_id="run-2", kind="Formalizer",
                             target_id=str(g2), target_kind="Goal")
    # A finished row must never be touched.
    db.record_pipeline_start(conn, pipeline_id="done-1", kind="Formalizer",
                             target_id=str(g1), target_kind="Goal")
    db.finish_pipeline(conn, pipeline_id="done-1", status="succeeded",
                       outcome="proved")

    recovery.recover_at_startup(conn, workspace=None, scope="p_one")
    st = {r["id"]: (r["status"], r["outcome"]) for r in conn.execute(
        "SELECT id, status, outcome FROM pipelines")}
    assert st["run-1"] == ("failed", "daemon_crashed")
    assert st["run-2"] == ("running", None)      # out of scope — untouched
    assert st["done-1"] == ("succeeded", "proved")

    recovery.recover_at_startup(conn, workspace=None, scope=None)
    st = {r["id"]: (r["status"], r["outcome"]) for r in conn.execute(
        "SELECT id, status, outcome FROM pipelines")}
    assert st["run-2"] == ("failed", "daemon_crashed")
    assert st["done-1"] == ("succeeded", "proved")
    conn.close()


def test_recovery_spares_live_concurrent_drivers_running_row(
        tmp_path: Path) -> None:
    """#90 analogue for pipelines rows: a 'running' row whose
    .attempts/<pid>/sandbox manifest names a LIVE owner belongs to a
    concurrent non-daemon driver — recovery must leave it alone. A dead
    owner (or no manifest at all) is a genuine orphan and is finalized."""
    from Tooling.agent.sandbox import MANIFEST_NAME
    conn = _fresh(tmp_path, "rec_live.db")
    gid = _seed_problem_goal(conn, "p_live")
    db.record_pipeline_start(conn, pipeline_id="live-1", kind="Formalizer",
                             target_id=str(gid), target_kind="Goal")
    db.record_pipeline_start(conn, pipeline_id="dead-1", kind="Formalizer",
                             target_id=str(gid), target_kind="Goal")
    live_dir = tmp_path / ".attempts" / "live-1" / "sandbox"
    live_dir.mkdir(parents=True)
    (live_dir / MANIFEST_NAME).write_text(
        json.dumps({"owner_pid": os.getpid()}), encoding="utf-8")

    recovery.recover_at_startup(conn, workspace=tmp_path, scope=None)
    st = {r["id"]: (r["status"], r["outcome"]) for r in conn.execute(
        "SELECT id, status, outcome FROM pipelines")}
    assert st["live-1"] == ("running", None)     # live owner — spared
    assert st["dead-1"] == ("failed", "daemon_crashed")
    conn.close()
