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


def test_fresh_db_is_latest(tmp_path):
    c = _fresh(tmp_path)
    assert c.execute("PRAGMA user_version").fetchone()[0] == 9


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

    db.init_schema(c)  # re-run migrations → phase7 + phase8 fire

    assert c.execute("PRAGMA user_version").fetchone()[0] == 9
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
    assert c.execute("PRAGMA user_version").fetchone()[0] == 9


# --- Phase 8: library_decls.lifecycle accepts 'cleaned' ---

def _seed_lib_decl(c, slug, lifecycle):
    c.execute("INSERT INTO problems (name, manifest_path, created_at,"
              " bootstrap_done) VALUES ('p','',?,1)", (db.now(),))
    c.execute("INSERT INTO library_decls (problem, slug, lifecycle,"
              " created_at, updated_at) VALUES ('p',?,?,?,?)",
              (slug, lifecycle, db.now(), db.now()))


def test_fresh_db_library_decls_accepts_cleaned(tmp_path):
    c = _fresh(tmp_path)
    _seed_lib_decl(c, "foo", "cleaned")
    c.commit()
    assert c.execute("SELECT count(*) FROM library_decls WHERE"
                     " lifecycle='cleaned'").fetchone()[0] == 1


def test_library_decls_still_rejects_unknown_lifecycle(tmp_path):
    c = _fresh(tmp_path)
    with pytest.raises(sqlite3.IntegrityError):
        _seed_lib_decl(c, "bar", "bogus")


def test_v7_library_decls_upgrades_to_cleaned(tmp_path):
    """An old v7 DB with a 'migrated' library_decls row upgrades to v8,
    keeps the row, and then accepts 'cleaned'."""
    c = _fresh(tmp_path)
    _seed_lib_decl(c, "keep", "migrated")
    c.execute("PRAGMA user_version = 7")
    c.commit()

    db.init_schema(c)  # phase8 fires → rebuild library_decls

    assert c.execute("PRAGMA user_version").fetchone()[0] == 9
    assert c.execute("SELECT lifecycle FROM library_decls WHERE slug='keep'"
                     ).fetchone()[0] == "migrated"     # row preserved
    db.mark_library_cleaned(c, problem="p", slug="keep")
    assert c.execute("SELECT lifecycle FROM library_decls WHERE slug='keep'"
                     ).fetchone()[0] == "cleaned"      # CHECK widened
