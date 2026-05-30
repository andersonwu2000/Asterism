"""library_decls table + Librarian per-decl state helpers (plan §7)."""
from __future__ import annotations

import pytest

from Tooling.state import db


@pytest.fixture
def conn():
    c = db.connect(":memory:")
    db.init_schema(c)
    c.execute(
        "INSERT INTO problems (name, manifest_path, created_at, "
        "bootstrap_done) VALUES ('p', '', ?, 1)", (db.now(),))
    c.commit()
    return c


def _goal(conn, slug):
    return db.insert_goal(conn, problem="p", slug=slug,
                          lean_path=f"proofs/L_{slug}.lean",
                          statement="True", origin="backward",
                          kind="theorem")


# ---------------------------------------------------------------------
# schema present
# ---------------------------------------------------------------------

def test_table_and_index_exist(conn):
    names = {r["name"] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table','index')")}
    assert "library_decls" in names
    assert "idx_libdecls_problem" in names


# ---------------------------------------------------------------------
# upsert
# ---------------------------------------------------------------------

def test_upsert_creates_candidate(conn):
    gid = _goal(conn, "lemma_a")
    rid = db.upsert_library_decl(conn, problem="p", slug="lemma_a",
                                 source_goal_id=gid)
    row = conn.execute("SELECT * FROM library_decls WHERE id = ?",
                       (rid,)).fetchone()
    assert row["slug"] == "lemma_a"
    assert row["lifecycle"] == "candidate"
    assert row["source_goal_id"] == gid


def test_upsert_idempotent(conn):
    gid = _goal(conn, "lemma_a")
    r1 = db.upsert_library_decl(conn, problem="p", slug="lemma_a",
                                source_goal_id=gid)
    r2 = db.upsert_library_decl(conn, problem="p", slug="lemma_a",
                                source_goal_id=gid)
    assert r1 == r2
    n = conn.execute("SELECT COUNT(*) FROM library_decls").fetchone()[0]
    assert n == 1


def test_upsert_preserves_verdict_on_reentry(conn):
    """Re-running inventory must not wipe a verdict already set."""
    db.upsert_library_decl(conn, problem="p", slug="x", source_goal_id=None)
    db.set_library_verdict(conn, problem="p", slug="x", verdict="keep")
    db.upsert_library_decl(conn, problem="p", slug="x", source_goal_id=None)
    row = conn.execute("SELECT verdict, lifecycle FROM library_decls "
                       "WHERE slug='x'").fetchone()
    assert row["verdict"] == "keep"
    assert row["lifecycle"] == "deduped"


# ---------------------------------------------------------------------
# verdict → lifecycle mapping
# ---------------------------------------------------------------------

@pytest.mark.parametrize("verdict,expected", [
    ("keep", "deduped"),
    ("cite-mathlib", "cited"),
    ("cite-library", "cited"),
    ("drop", "dropped"),
    ("merge", "dropped"),
])
def test_verdict_lifecycle_mapping(conn, verdict, expected):
    db.upsert_library_decl(conn, problem="p", slug="x", source_goal_id=None)
    db.set_library_verdict(conn, problem="p", slug="x", verdict=verdict,
                           citation="some_mathlib_lemma")
    row = conn.execute("SELECT verdict, citation, lifecycle FROM "
                       "library_decls WHERE slug='x'").fetchone()
    assert row["verdict"] == verdict
    assert row["lifecycle"] == expected
    assert row["citation"] == "some_mathlib_lemma"


# ---------------------------------------------------------------------
# classify + migrate lifecycle progression
# ---------------------------------------------------------------------

def test_classify_advances_kept_decl(conn):
    db.upsert_library_decl(conn, problem="p", slug="x", source_goal_id=None)
    db.set_library_verdict(conn, problem="p", slug="x", verdict="keep")
    db.set_library_classification(conn, problem="p", slug="x",
                                  target_file="Library/Algebra/X.lean",
                                  target_name="myLemma", file_order=2)
    row = conn.execute("SELECT * FROM library_decls WHERE slug='x'").fetchone()
    assert row["lifecycle"] == "classified"
    assert row["target_file"] == "Library/Algebra/X.lean"
    assert row["target_name"] == "myLemma"
    assert row["file_order"] == 2


def test_classify_noop_on_dropped(conn):
    """A dropped decl must not be classified."""
    db.upsert_library_decl(conn, problem="p", slug="x", source_goal_id=None)
    db.set_library_verdict(conn, problem="p", slug="x", verdict="drop")
    db.set_library_classification(conn, problem="p", slug="x",
                                  target_file="f", target_name=None,
                                  file_order=0)
    row = conn.execute("SELECT lifecycle, target_file FROM library_decls "
                       "WHERE slug='x'").fetchone()
    assert row["lifecycle"] == "dropped"
    assert row["target_file"] is None


def test_migrate_advances_classified(conn):
    db.upsert_library_decl(conn, problem="p", slug="x", source_goal_id=None)
    db.set_library_verdict(conn, problem="p", slug="x", verdict="keep")
    db.set_library_classification(conn, problem="p", slug="x",
                                  target_file="f", target_name=None,
                                  file_order=0)
    db.mark_library_migrated(conn, problem="p", slug="x")
    row = conn.execute("SELECT lifecycle FROM library_decls "
                       "WHERE slug='x'").fetchone()
    assert row["lifecycle"] == "migrated"


def test_migrate_noop_on_unclassified(conn):
    """Can't migrate something never classified."""
    db.upsert_library_decl(conn, problem="p", slug="x", source_goal_id=None)
    db.set_library_verdict(conn, problem="p", slug="x", verdict="keep")
    db.mark_library_migrated(conn, problem="p", slug="x")
    row = conn.execute("SELECT lifecycle FROM library_decls "
                       "WHERE slug='x'").fetchone()
    assert row["lifecycle"] == "deduped"  # unchanged


# ---------------------------------------------------------------------
# query
# ---------------------------------------------------------------------

def test_library_decls_for_filters_lifecycle(conn):
    for s, v in [("a", "keep"), ("b", "drop"), ("c", "keep")]:
        db.upsert_library_decl(conn, problem="p", slug=s, source_goal_id=None)
        db.set_library_verdict(conn, problem="p", slug=s, verdict=v)
    all_decls = db.library_decls_for(conn, "p")
    assert len(all_decls) == 3
    deduped = db.library_decls_for(conn, "p", lifecycle="deduped")
    assert {r["slug"] for r in deduped} == {"a", "c"}
    dropped = db.library_decls_for(conn, "p", lifecycle="dropped")
    assert {r["slug"] for r in dropped} == {"b"}


def test_bad_lifecycle_rejected_by_check(conn):
    """The CHECK constraint guards the lifecycle enum."""
    import sqlite3
    db.upsert_library_decl(conn, problem="p", slug="x", source_goal_id=None)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE library_decls SET lifecycle='bogus' "
                     "WHERE slug='x'")
