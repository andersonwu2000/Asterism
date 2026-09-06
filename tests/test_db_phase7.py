"""Phase 7 migration: pipelines.kind + queue.kind CHECK accept 'Librarian'.

Guards the schema contract the Librarian dispatch trigger depends on — a
fresh DB is at the expected version and accepts the new kind, an old (v6)
DB upgrades in place without losing rows, and re-running init_schema is a
no-op. Invariant test per CLAUDE.md rule 6 (schema CHECKs get tests too).
"""
import re
import sqlite3

import pytest

from Tooling.state import db

# The terminal `user_version` pinned below steps with
# `db._CURRENT_USER_VERSION`. 48→49 2026-09-02: HID §3.7's `Signal`
# widens `human_commands.kind`, and SQLite takes a widened CHECK only
# as a table rebuild — hence a version step. 49→50 2026-09-03:
# `strategist_decisions.report_carried_at`, the batch-report carry-over
# mark — an additive column, and since v15 those ship as version steps
# too (the frozen block below is why). 50→51 2026-09-04: the goal status
# `dead` is retired, which narrows the `goals.status` CHECK — another
# rebuild, and the migration also rewrites the surviving rows. 51→52
# 2026-09-04: the Theorist layer (theory_wake_design.md §4) - four
# CHECK widenings and one new table. 52→53 2026-09-06:
# `strategist_decisions.infra_deaths` — the bound on re-queueing a
# request whose worker died on infra.


def _fresh(tmp_path):
    c = db.connect(tmp_path / "t.db")
    db.init_schema(c)
    return c


def test_fresh_db_is_latest(tmp_path):
    c = _fresh(tmp_path)
    assert c.execute("PRAGMA user_version").fetchone()[0] == 55


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

    assert c.execute("PRAGMA user_version").fetchone()[0] == 55
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
    assert c.execute("PRAGMA user_version").fetchone()[0] == 55


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

    assert c.execute("PRAGMA user_version").fetchone()[0] == 55
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

    assert c.execute("PRAGMA user_version").fetchone()[0] == 55
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

    assert c.execute("PRAGMA user_version").fetchone()[0] == 55
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


# --- v51: the goal status `dead` is retired (owner ruling 2026-09-04) ---

def _downgrade_goals_check_to_v50(c) -> None:
    """Rebuild `goals` with the pre-v51 CHECK (which still accepted
    'dead') so the migration has something real to convert. The mirror
    image of `_migrate_to_v51`'s own live-DDL rebuild."""
    sql = c.execute("SELECT sql FROM sqlite_master WHERE type='table'"
                    " AND name='goals'").fetchone()[0]
    check = re.search(r"CHECK\(status IN \(([^)]*)\)\)", sql)
    assert check and "'dead'" not in check.group(1), \
        "fresh schema still mints 'dead' goals"
    wide = sql.replace("'frozen')", "'frozen','dead')", 1)
    assert wide != sql, "goals.status CHECK no longer ends at 'frozen'"
    idx = [r[0] for r in c.execute(
        "SELECT sql FROM sqlite_master WHERE type='index'"
        " AND tbl_name='goals' AND sql IS NOT NULL")]
    c.execute("PRAGMA foreign_keys = OFF")
    c.execute(wide.replace("CREATE TABLE goals", "CREATE TABLE _g_old", 1))
    c.execute("INSERT INTO _g_old SELECT * FROM goals")
    c.execute("DROP TABLE goals")
    c.execute("ALTER TABLE _g_old RENAME TO goals")
    for s in idx:
        c.execute(s)
    c.execute("PRAGMA foreign_keys = ON")
    c.execute("PRAGMA user_version = 50")
    c.commit()


def _seed_goal_v50(c, slug, status):
    c.execute("INSERT INTO goals (problem, slug, lean_path, statement,"
              " kind, origin, status, depth, attempts, created_at,"
              " updated_at) VALUES ('p',?,?, 'T','theorem','backward',?,"
              " 0,0,?,?)",
              (slug, f"Problems/p/proofs/L_{slug}.lean", status,
               db.now(), db.now()))
    c.commit()
    return c.execute("SELECT id FROM goals WHERE slug = ?", (slug,)
                     ).fetchone()[0]


def test_v51_maps_dead_goals_to_shelved_with_a_history_row(tmp_path):
    """A goal is a statement and only the kernel settles one, so `dead`
    leaves the vocabulary. Existing rows become parks — and each one
    gets a `goal_events` row naming the status it left, so the history
    reads the same after the rename as before it."""
    c = _fresh(tmp_path)
    c.execute("INSERT INTO problems (name, created_at, bootstrap_done)"
              " VALUES ('p',?,1)", (db.now(),))
    c.commit()
    _downgrade_goals_check_to_v50(c)
    gid = _seed_goal_v50(c, "moot_ctx", "dead")
    keep = _seed_goal_v50(c, "still_open", "open")

    db.init_schema(c)

    assert c.execute("PRAGMA user_version").fetchone()[0] == 55
    assert c.execute("SELECT status FROM goals WHERE id = ?",
                     (gid,)).fetchone()[0] == "shelved"
    assert c.execute("SELECT status FROM goals WHERE id = ?",
                     (keep,)).fetchone()[0] == "open"
    ev = c.execute(
        "SELECT from_status, to_status, event, reason FROM goal_events"
        " WHERE goal_id = ?", (gid,)).fetchone()
    assert ev is not None
    assert (ev[0], ev[1], ev[2]) == ("dead", "shelved", "retire_dead_status")
    assert "dead" in ev[3]
    # Untouched goals get no invented history.
    assert c.execute("SELECT count(*) FROM goal_events WHERE goal_id = ?",
                     (keep,)).fetchone()[0] == 0
    # And the narrowed CHECK now refuses a fresh one.
    with pytest.raises(sqlite3.IntegrityError):
        _seed_goal_v50(c, "rogue", "dead")


def test_v51_is_idempotent_on_a_dead_free_db(tmp_path):
    c = _fresh(tmp_path)
    db.init_schema(c)
    assert c.execute("PRAGMA user_version").fetchone()[0] == 55
    assert c.execute("SELECT count(*) FROM goal_events").fetchone()[0] == 0


# -- v52: the Theorist layer (theory_wake_design.md 4) ----------------

def _downgrade_to_v51(c) -> None:
    """Put a fresh disk back to the v51 shape: the four CHECKs without
    their new value, and no `theory_documents`. The rebuilds are the
    same live-DDL edit the migration uses, run backwards, so the
    fixture cannot drift from the table it is pretending to be."""
    c.execute("PRAGMA foreign_keys = OFF")
    for table, old, new in (
            ("strategist_decisions", "'CloseGroup','Theorize')",
             "'CloseGroup')"),
            ("pipelines", "'Scholar','Formalizer','Theorist')",
             "'Scholar','Formalizer')"),
            ("queue", "'Scholar','Formalizer','Theorist')",
             "'Scholar','Formalizer')"),
            ("human_commands", "'Signal','Theory')", "'Signal')"),
            ("problem_papers", "'presearch','theorist')",
             "'presearch')")):
        sql = c.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
            (table,)).fetchone()[0]
        assert old in sql, (table, sql)
        idx = [r[0] for r in c.execute(
            "SELECT sql FROM sqlite_master WHERE type='index'"
            " AND tbl_name=? AND sql IS NOT NULL", (table,))]
        tmp = "_%s_old" % table
        c.execute("DROP TABLE IF EXISTS %s" % tmp)
        c.execute(re.sub(r'CREATE TABLE\s+"?%s"?' % table,
                         "CREATE TABLE %s" % tmp,
                         sql.replace(old, new, 1), count=1))
        c.execute("INSERT INTO %s SELECT * FROM %s" % (tmp, table))
        c.execute("DROP TABLE %s" % table)
        c.execute("ALTER TABLE %s RENAME TO %s" % (tmp, table))
        for s in idx:
            c.execute(s)
    c.execute("DROP TABLE IF EXISTS theory_documents")
    c.execute("PRAGMA foreign_keys = ON")
    c.execute("PRAGMA user_version = 51")
    c.commit()


def test_v52_widens_the_four_checks_the_theory_layer_needs(tmp_path):
    """A `Theorize` decision, the `Theorist` pipeline and queue row it
    dispatches, the human `Theory` command that can file one, and the
    papers the author binds - each is a value in a CHECK SQLite cannot
    widen in place, so all of them ride one version step."""
    c = _fresh(tmp_path)
    c.execute("INSERT INTO problems (name, created_at, bootstrap_done)"
              " VALUES ('p',?,1)", (db.now(),))
    c.commit()
    _downgrade_to_v51(c)
    assert c.execute("PRAGMA user_version").fetchone()[0] == 51

    db.init_schema(c)
    assert c.execute("PRAGMA user_version").fetchone()[0] == 55
    ts = db.now()
    c.execute("INSERT INTO strategist_decisions (problem,"
              " triggered_at_tick, trigger_kind, decision_kind, payload,"
              " created_at, updated_at) VALUES ('p',0,'routine',"
              " 'Theorize','{}',?,?)", (ts, ts))
    c.execute("INSERT INTO pipelines (id, kind, target_id, target_kind,"
              " status, started_at) VALUES ('pid','Theorist','1','Group',"
              " 'running',?)", (ts,))
    c.execute("INSERT INTO queue (kind, target_id, target_kind, problem,"
              " created_at) VALUES ('Theorist','1','Group','p',?)", (ts,))
    c.execute("INSERT INTO human_commands (problem, kind, payload,"
              " idempotency_key, status, created_at)"
              " VALUES ('p','Theory','{}','k','queued',?)", (ts,))
    c.execute("INSERT INTO problem_papers (problem, paper_id, origin,"
              " created_at) VALUES ('p','a1','theorist',?)", (ts,))
    c.commit()


def test_v52_carries_the_rows_it_rebuilds(tmp_path):
    """`human_commands` and `queue` are LIVE state - a command a person
    queued seconds before the step is still their command."""
    c = _fresh(tmp_path)
    c.execute("INSERT INTO problems (name, created_at, bootstrap_done)"
              " VALUES ('p',?,1)", (db.now(),))
    c.commit()
    _downgrade_to_v51(c)
    ts = db.now()
    c.execute("INSERT INTO human_commands (problem, kind, payload,"
              " idempotency_key, status, created_at)"
              " VALUES ('p','Inject','{}','keep','queued',?)", (ts,))
    c.execute("INSERT INTO queue (kind, target_id, target_kind, problem,"
              " created_at) VALUES ('Formalizer','p','Problem','p',?)",
              (ts,))
    c.commit()

    db.init_schema(c)
    assert c.execute("SELECT idempotency_key FROM human_commands"
                     ).fetchone()[0] == "keep"
    assert c.execute("SELECT kind FROM queue").fetchone()[0] == "Formalizer"
    # the UNIQUE that makes a retried command the same command survives
    with pytest.raises(sqlite3.IntegrityError):
        c.execute("INSERT INTO human_commands (problem, kind, payload,"
                  " idempotency_key, status, created_at)"
                  " VALUES ('p','Inject','{}','keep','queued',?)", (ts,))


def test_v52_mints_theory_documents(tmp_path):
    """The Theorist's product is a DOCUMENT - the one artifact the
    decision log had no table for. Status is the review's verdict, and
    a rejected run keeps its row (the verdict is the evidence) with no
    path."""
    c = _fresh(tmp_path)
    c.execute("INSERT INTO problems (name, created_at, bootstrap_done)"
              " VALUES ('p',?,1)", (db.now(),))
    c.commit()
    _downgrade_to_v51(c)
    db.init_schema(c)
    cols = {r[1] for r in c.execute("PRAGMA table_info(theory_documents)")}
    assert cols == {"id", "problem", "group_id", "pipeline_id",
                    "decision_id", "objective", "situation", "path",
                    "status", "rounds", "verdict_json", "created_at"}
    ts = db.now()
    c.execute("INSERT INTO theory_documents (problem, objective,"
              " situation, status, rounds, created_at)"
              " VALUES ('p','o','s','accepted',1,?)", (ts,))
    c.execute("INSERT INTO theory_documents (problem, objective,"
              " situation, status, rounds, created_at)"
              " VALUES ('p','o','s','rejected',3,?)", (ts,))
    c.commit()
    with pytest.raises(sqlite3.IntegrityError):
        c.execute("INSERT INTO theory_documents (problem, objective,"
                  " situation, status, rounds, created_at)"
                  " VALUES ('p','o','s','maybe',1,?)", (ts,))


def test_v52_is_idempotent(tmp_path):
    c = _fresh(tmp_path)
    db.init_schema(c)
    db.init_schema(c)
    assert c.execute("PRAGMA user_version").fetchone()[0] == 55


# -- v55: user_file_history.source gains 'framework' ------------------


def _downgrade_to_v54(c) -> None:
    """The v54 shape of `user_file_history`: no 'framework' in the CHECK.
    The rebuild is the migration's own live-DDL edit run backwards, so
    the fixture cannot drift from the table it pretends to be."""
    sql = c.execute("SELECT sql FROM sqlite_master WHERE type='table'"
                    " AND name='user_file_history'").fetchone()[0]
    assert "'repin', 'framework'" in sql, sql
    c.execute("PRAGMA foreign_keys = OFF")
    c.execute("DROP TABLE IF EXISTS _ufh_old")
    c.execute(re.sub(r'CREATE TABLE\s+"?user_file_history"?',
                     "CREATE TABLE _ufh_old",
                     sql.replace("'repin', 'framework'", "'repin'", 1),
                     count=1))
    c.execute("INSERT INTO _ufh_old SELECT * FROM user_file_history")
    c.execute("DROP TABLE user_file_history")
    c.execute("ALTER TABLE _ufh_old RENAME TO user_file_history")
    c.execute("PRAGMA foreign_keys = ON")
    c.execute("PRAGMA user_version = 54")
    c.commit()


def test_v55_widens_user_file_history_source_and_carries_its_rows(tmp_path):
    """The framework writes Root.lean itself (Verify's promotion to the
    `def main := @s<N>` alias). Without a source that says so, the sweep
    watching those bytes for a HUMAN edit filed the machine's own write
    as an observation and warned that the review/root gate would surface
    it (Lab.even_sum_subsets, 2026-09-07). The history is the record, so
    the rebuild carries every row."""
    c = _fresh(tmp_path)
    ts = db.now()
    c.execute("INSERT INTO problems (name, created_at, bootstrap_done)"
              " VALUES ('p',?,1)", (ts,))
    c.commit()
    _downgrade_to_v54(c)
    c.execute("INSERT INTO user_file_history (problem, file, sha, body,"
              " seen_at, source) VALUES ('p','Root.lean','aa','stub',?,"
              "'observed')", (ts,))
    c.commit()
    with pytest.raises(sqlite3.IntegrityError):
        c.execute("INSERT INTO user_file_history (problem, file, sha, body,"
                  " seen_at, source) VALUES ('p','Root.lean','bb','alias',?,"
                  "'framework')", (ts,))

    db.init_schema(c)
    assert c.execute("PRAGMA user_version").fetchone()[0] == 55
    assert c.execute("SELECT sha FROM user_file_history").fetchone()[0] == "aa"
    c.execute("INSERT INTO user_file_history (problem, file, sha, body,"
              " seen_at, source) VALUES ('p','Root.lean','bb','alias',?,"
              "'framework')", (ts,))
    c.commit()
    with pytest.raises(sqlite3.IntegrityError):
        c.execute("INSERT INTO user_file_history (problem, file, sha, body,"
                  " seen_at, source) VALUES ('p','Root.lean','cc','x',?,"
                  "'guess')", (ts,))


def test_v55_is_idempotent_and_matches_a_fresh_disk(tmp_path):
    c = _fresh(tmp_path)
    db.init_schema(c)
    fresh_sql = c.execute("SELECT sql FROM sqlite_master WHERE type='table'"
                          " AND name='user_file_history'").fetchone()[0]
    _downgrade_to_v54(c)
    db.init_schema(c)
    db.init_schema(c)
    got = c.execute("SELECT sql FROM sqlite_master WHERE type='table'"
                    " AND name='user_file_history'").fetchone()[0]
    # ALTER TABLE ... RENAME quotes the name it writes; everything the
    # constraint says is what this compares.
    assert got.replace('"user_file_history"', "user_file_history") == fresh_sql
    assert c.execute("PRAGMA user_version").fetchone()[0] == 55
