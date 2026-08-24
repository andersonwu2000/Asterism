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
    assert c.execute("PRAGMA user_version").fetchone()[0] == 43


def test_queue_accepts_librarian(tmp_path):
    c = _fresh(tmp_path)
    c.execute("INSERT INTO problems (name, created_at,"
              " bootstrap_done) VALUES ('p',?,1)", (db.now(),))
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
    c.execute("INSERT INTO problems (name, created_at,"
              " bootstrap_done) VALUES ('p',?,1)", (db.now(),))
    c.execute("INSERT INTO queue (kind, target_id, target_kind, priority,"
              " created_at) VALUES ('Builder','5','Goal',5,?)", (db.now(),))
    c.execute("INSERT INTO pipelines (id, kind, target_id, target_kind,"
              " status, outcome, started_at, finished_at)"
              " VALUES ('p1','Backward','5','Goal','succeeded','proved',"
              "'t','t')")
    c.execute("PRAGMA user_version = 6")
    c.commit()

    db.init_schema(c)  # re-run migrations → phase7 + phase8 fire

    assert c.execute("PRAGMA user_version").fetchone()[0] == 43
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
    assert c.execute("PRAGMA user_version").fetchone()[0] == 43


# --- Phase 8: library_decls.lifecycle accepts 'cleaned' ---

def _seed_lib_decl(c, slug, lifecycle):
    c.execute("INSERT INTO problems (name, created_at,"
              " bootstrap_done) VALUES ('p',?,1)", (db.now(),))
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

    assert c.execute("PRAGMA user_version").fetchone()[0] == 43
    assert c.execute("SELECT lifecycle FROM library_decls WHERE slug='keep'"
                     ).fetchone()[0] == "migrated"     # row preserved
    db.mark_library_cleaned(c, problem="p", slug="keep")
    assert c.execute("SELECT lifecycle FROM library_decls WHERE slug='keep'"
                     ).fetchone()[0] == "cleaned"      # CHECK widened


# --- Phase 10: library_decls.renamed_from (P4 rename deferred-rewire) ---

def test_fresh_db_has_renamed_from(tmp_path):
    c = _fresh(tmp_path)
    cols = {r[1] for r in c.execute("PRAGMA table_info(library_decls)")}
    assert "renamed_from" in cols


def test_v9_db_gains_renamed_from(tmp_path):
    """An old v9 DB (library_decls without renamed_from) upgrades to v10 via a
    plain ADD COLUMN, keeping rows."""
    c = _fresh(tmp_path)
    _seed_lib_decl(c, "keep", "migrated")
    c.execute("ALTER TABLE library_decls DROP COLUMN renamed_from")
    c.execute("PRAGMA user_version = 9")
    c.commit()
    assert "renamed_from" not in {
        r[1] for r in c.execute("PRAGMA table_info(library_decls)")}

    db.init_schema(c)  # phase10 fires → ADD COLUMN

    assert c.execute("PRAGMA user_version").fetchone()[0] == 43
    assert "renamed_from" in {
        r[1] for r in c.execute("PRAGMA table_info(library_decls)")}
    assert c.execute("SELECT lifecycle FROM library_decls WHERE slug='keep'"
                     ).fetchone()[0] == "migrated"     # row preserved


def test_set_library_renamed_records_old_and_new(tmp_path):
    c = _fresh(tmp_path)
    _seed_lib_decl(c, "foo", "cleaned")
    c.execute("UPDATE library_decls SET target_name='Library.M.old_name'"
              " WHERE slug='foo'")
    c.commit()
    db.set_library_renamed(c, problem="p", slug="foo",
                           old_fqn="Library.M.old_name",
                           new_fqn="Library.M.new_name")
    row = c.execute("SELECT target_name, renamed_from FROM library_decls"
                    " WHERE slug='foo'").fetchone()
    assert row["target_name"] == "Library.M.new_name"
    assert row["renamed_from"] == "Library.M.old_name"
    # COALESCE: a second rename keeps the ORIGINAL renamed_from.
    db.set_library_renamed(c, problem="p", slug="foo",
                           old_fqn="Library.M.new_name",
                           new_fqn="Library.M.newer_name")
    row = c.execute("SELECT target_name, renamed_from FROM library_decls"
                    " WHERE slug='foo'").fetchone()
    assert row["target_name"] == "Library.M.newer_name"
    assert row["renamed_from"] == "Library.M.old_name"   # earliest preserved


# --- v16: problems.ingested_at (Phase 6 problem terminal state) ---

def test_fresh_db_has_ingested_at(tmp_path):
    c = _fresh(tmp_path)
    cols = {r[1] for r in c.execute("PRAGMA table_info(problems)")}
    assert "ingested_at" in cols


def test_v15_db_gains_ingested_at_with_legacy_backfill(tmp_path):
    """A v15 DB upgrades via ADD COLUMN; legacy problems whose root is
    proved+integrity_verified are backfilled as ingested (decision ②:
    old completed runs must not re-trigger as stalled), live ones stay
    NULL."""
    c = _fresh(tmp_path)
    c.execute("INSERT INTO problems (name, created_at)"
              " VALUES ('done',?)", (db.now(),))
    c.execute("INSERT INTO problems (name, created_at)"
              " VALUES ('live',?)", (db.now(),))
    c.execute("INSERT INTO goals (problem, slug, lean_path, statement,"
              " origin, status, integrity_verified, created_at, updated_at)"
              " VALUES ('done','main','a.lean','True','root','proved',1,?,?)",
              (db.now(), db.now()))
    c.execute("INSERT INTO goals (problem, slug, lean_path, statement,"
              " origin, status, created_at, updated_at) VALUES"
              " ('live','main','b.lean','True','root','open',?,?)",
              (db.now(), db.now()))
    # Simulate the v15 problems table by rebuild (DROP COLUMN chokes on
    # the CREATE-text comments adjacent to the last column).
    c.commit()  # PRAGMA foreign_keys is a no-op inside a transaction
    c.execute("PRAGMA foreign_keys=OFF")
    c.execute("PRAGMA legacy_alter_table=ON")
    c.execute("ALTER TABLE problems RENAME TO problems_v15")
    c.execute("CREATE TABLE problems ("
              " name TEXT PRIMARY KEY, manifest_path TEXT NOT NULL,"
              " created_at TEXT NOT NULL,"
              " bootstrap_done INTEGER NOT NULL DEFAULT 0,"
              " strategist_directive TEXT, last_strategist_at TEXT,"
              " last_routine_at TEXT,"
              " ingest_signoff_pending INTEGER NOT NULL DEFAULT 0)")
    c.execute("INSERT INTO problems (name, manifest_path, created_at)"
              " SELECT name, '', created_at FROM problems_v15")
    c.execute("DROP TABLE problems_v15")
    c.execute("PRAGMA user_version = 15")
    c.commit()

    db.init_schema(c)  # v16 fires → ADD COLUMN + backfill

    assert c.execute("PRAGMA user_version").fetchone()[0] == 43
    assert c.execute("SELECT ingested_at FROM problems WHERE name='done'"
                     ).fetchone()[0] is not None
    assert c.execute("SELECT ingested_at FROM problems WHERE name='live'"
                     ).fetchone()[0] is None


def test_set_problem_ingested_roundtrip(tmp_path):
    c = _fresh(tmp_path)
    c.execute("INSERT INTO problems (name, created_at)"
              " VALUES ('p',?)", (db.now(),))
    c.commit()
    assert not db.problem_ingested(c, "p")
    db.set_problem_ingested(c, "p")
    assert db.problem_ingested(c, "p")
    db.set_problem_ingested(c, "p", ingested=False)   # rollback auto-revoke
    assert not db.problem_ingested(c, "p")


def test_all_problems_ingested_scope(tmp_path):
    c = _fresh(tmp_path)
    for name in ("a.x", "a.y", "b.z"):
        c.execute("INSERT INTO problems (name, created_at)"
                  " VALUES (?,?)", (name, db.now()))
    c.commit()
    assert not db.all_problems_ingested(c, scope="a.%")
    db.set_problem_ingested(c, "a.x")
    db.set_problem_ingested(c, "a.y")
    assert db.all_problems_ingested(c, scope="a.%")
    assert not db.all_problems_ingested(c)            # b.z still live
    assert not db.all_problems_ingested(c, scope="nomatch.%")  # vacuous → False


def test_additive_alter_block_is_frozen():
    """v15 policy (task #10): the unversioned blind-ALTER block is FROZEN.
    Versions ≤14 grew columns through it with "no user_version bump needed"
    notes, making user_version an incomplete description of a DB. From v15
    every new column ships as a versioned migration step — growing this
    block trips here; shrinking it (a column folded into a rebuild) means
    lowering the pin consciously."""
    import inspect
    from Tooling.state import db_migrations
    src = inspect.getsource(db_migrations._apply_locked)
    start = src.index("for col, ddl in (")
    end = src.index("):", start)
    # count DDL strings, not the words (comments inside the block
    # legitimately say "ADD COLUMN")
    n = src[start:end].count('"ALTER TABLE ')
    assert n == 13, (
        f"legacy additive ALTER block has {n} entries (pin: 13) — new "
        "columns must ship as a VERSIONED migration step (see the v15 "
        "stamp comment), not by growing this block")


# ---------------------------------------------------------------------
# insert_goal writes `detached` in the same INSERT (2026-07-04 convention
# audit, finding 2: the follow-up set_goal_detached pairing was
# duplicated-by-discipline across every Forward commit path; a forgotten
# pairing is a silent stuck goal only offline drift-check catches).
# ---------------------------------------------------------------------

def test_insert_goal_forward_origin_is_detached() -> None:
    conn = db.connect(":memory:")
    db.init_schema(conn)
    conn.execute("INSERT INTO problems (name, created_at,"
                 " bootstrap_done) VALUES ('p', '', 1)")
    fwd = db.insert_goal(conn, problem="p", slug="f", lean_path="a.lean",
                         statement="s", origin="forward")
    bwd = db.insert_goal(conn, problem="p", slug="b", lean_path="b.lean",
                         statement="s", origin="backward")
    assert conn.execute("SELECT detached FROM goals WHERE id=?",
                        (fwd,)).fetchone()[0] == 1
    assert conn.execute("SELECT detached FROM goals WHERE id=?",
                        (bwd,)).fetchone()[0] == 0
