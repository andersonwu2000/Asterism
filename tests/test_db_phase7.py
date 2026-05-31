"""Phase 7 migration: pipelines.kind + queue.kind CHECK accept 'Librarian'.

Guards the schema contract the Librarian dispatch trigger depends on — a
fresh DB is at the expected version and accepts the new kind, an old (v6)
DB upgrades in place without losing rows, and re-running init_schema is a
no-op. Invariant test per CLAUDE.md rule 6 (schema CHECKs get tests too).
"""
import sqlite3

import pytest

from Tooling.state import db


def _fresh(tmp_path):
    c = db.connect(tmp_path / "t.db")
    db.init_schema(c)
    return c


def test_fresh_db_is_phase7(tmp_path):
    c = _fresh(tmp_path)
    assert c.execute("PRAGMA user_version").fetchone()[0] == 7


def test_queue_accepts_librarian(tmp_path):
    c = _fresh(tmp_path)
    c.execute("INSERT INTO problems (name, manifest_path, created_at,"
              " bootstrap_done) VALUES ('p','',?,1)", (db.now(),))
    c.execute("INSERT INTO queue (kind, target_id, target_kind, priority,"
              " created_at) VALUES ('Librarian','p','Problem',5,?)",
              (db.now(),))
    c.commit()
    assert c.execute("SELECT count(*) FROM queue WHERE kind='Librarian'"
                     ).fetchone()[0] == 1


def test_pipelines_accepts_librarian(tmp_path):
    c = _fresh(tmp_path)
    c.execute("INSERT INTO pipelines (id, kind, target_id, target_kind,"
              " status, outcome, started_at, finished_at)"
              " VALUES ('x','Librarian','p','Problem','succeeded','success',"
              "'t','t')")
    c.commit()
    assert c.execute("SELECT count(*) FROM pipelines WHERE kind='Librarian'"
                     ).fetchone()[0] == 1


def test_queue_still_rejects_unknown_kind(tmp_path):
    c = _fresh(tmp_path)
    with pytest.raises(sqlite3.IntegrityError):
        c.execute("INSERT INTO queue (kind, target_id, target_kind,"
                  " priority, created_at)"
                  " VALUES ('Bogus','p','Problem',5,?)", (db.now(),))


def test_v6_upgrades_preserving_rows(tmp_path):
    """An old v6 DB with Builder/Backward rows upgrades to v7 in place,
    keeps every row, and then accepts 'Librarian'."""
    c = _fresh(tmp_path)
    c.execute("INSERT INTO problems (name, manifest_path, created_at,"
              " bootstrap_done) VALUES ('p','',?,1)", (db.now(),))
    c.execute("INSERT INTO queue (kind, target_id, target_kind, priority,"
              " created_at) VALUES ('Builder','5','Goal',5,?)", (db.now(),))
    c.execute("INSERT INTO pipelines (id, kind, target_id, target_kind,"
              " status, outcome, started_at, finished_at)"
              " VALUES ('p1','Backward','5','Goal','succeeded','proved',"
              "'t','t')")
    c.execute("PRAGMA user_version = 6")
    c.commit()

    db.init_schema(c)  # re-run migrations → phase7 fires

    assert c.execute("PRAGMA user_version").fetchone()[0] == 7
    assert c.execute("SELECT count(*) FROM queue").fetchone()[0] == 1
    assert c.execute("SELECT count(*) FROM pipelines").fetchone()[0] == 1
    c.execute("INSERT INTO queue (kind, target_id, target_kind, priority,"
              " created_at) VALUES ('Librarian','p','Problem',5,?)",
              (db.now(),))
    c.commit()  # no IntegrityError → CHECK widened


def test_reinit_is_idempotent(tmp_path):
    c = _fresh(tmp_path)
    db.init_schema(c)
    db.init_schema(c)
    assert c.execute("PRAGMA user_version").fetchone()[0] == 7
