"""Librarian dispatcher wiring — P0 phases 3 + 4.

Covers the derive-from-state routing, the race-safe re-enqueue chain,
and the terminal agentless `finish` step (INDEX provenance + chain
termination). These are the glue between the verify-hook enqueue
(phase 2) and the already-tested librarian work-kind cores.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from Tooling.state import db
from Tooling.core import dispatcher
from Tooling.pipeline import librarian


# ---------------------------------------------------------------------
# Seeding helpers — drive a decl through the lifecycle state machine.
# ---------------------------------------------------------------------

def _seed_problem(conn, name):
    # library_decls.problem FKs problems.name — seed before any upsert.
    if conn.execute("SELECT 1 FROM problems WHERE name = ?",
                    (name,)).fetchone() is None:
        conn.execute(
            "INSERT INTO problems (name, manifest_path, created_at,"
            " bootstrap_done) VALUES (?, ?, ?, 1)",
            (name, f"Problems/{name}/Manifest.md", db.now()))
        conn.commit()


def _mem() -> sqlite3.Connection:
    conn = db.connect(":memory:")
    db.init_schema(conn)
    return conn


def _candidate(conn, slug, problem="p"):
    _seed_problem(conn, problem)
    db.upsert_library_decl(conn, problem=problem, slug=slug,
                           source_goal_id=None)


def _deduped(conn, slug, problem="p"):
    _candidate(conn, slug, problem)
    db.set_library_verdict(conn, problem=problem, slug=slug, verdict="keep")


def _classified(conn, slug, problem="p", order=0):
    _deduped(conn, slug, problem)
    db.set_library_classification(
        conn, problem=problem, slug=slug,
        target_file=f"Library/P/{slug}.lean", target_name=slug,
        file_order=order)


def _migrated(conn, slug, problem="p", order=0):
    _classified(conn, slug, problem, order)
    db.mark_library_migrated(conn, problem=problem, slug=slug)


# ---------------------------------------------------------------------
# _derive_librarian_work — pure state → (work_kind, target_slug)
# ---------------------------------------------------------------------

def test_derive_no_rows_is_dedup(tmp_path: Path):
    conn = _mem()
    assert dispatcher._derive_librarian_work(conn, "p", tmp_path) == (
        "dedup", None)


def test_derive_candidate_is_dedup(tmp_path: Path):
    conn = _mem()
    _candidate(conn, "foo")
    assert dispatcher._derive_librarian_work(conn, "p", tmp_path) == (
        "dedup", None)


def test_derive_deduped_is_classify(tmp_path: Path):
    conn = _mem()
    _deduped(conn, "foo")
    assert dispatcher._derive_librarian_work(conn, "p", tmp_path) == (
        "classify", None)


def test_derive_classified_is_migrate_first_slug(tmp_path: Path):
    conn = _mem()
    # file_order drives "first" — seed out of order to prove ordering.
    _classified(conn, "bbb", order=1)
    _classified(conn, "aaa", order=0)
    work, slug = dispatcher._derive_librarian_work(conn, "p", tmp_path)
    assert work == "migrate"
    assert slug == "aaa"  # lowest file_order, not insertion order


def test_derive_migrated_no_index_is_finish(tmp_path: Path):
    conn = _mem()
    _migrated(conn, "foo")
    assert dispatcher._derive_librarian_work(conn, "p", tmp_path) == (
        "finish", None)


def test_derive_migrated_with_index_is_none(tmp_path: Path):
    conn = _mem()
    _migrated(conn, "foo")
    (tmp_path / "Library").mkdir()
    (tmp_path / "Library" / "INDEX.md").write_text(
        "# Library Index\n\n## p\n\nx\n", encoding="utf-8")
    assert dispatcher._derive_librarian_work(conn, "p", tmp_path) == (
        None, None)


def test_derive_all_terminal_cited_dropped_is_none(tmp_path: Path):
    conn = _mem()
    _candidate(conn, "a")
    db.set_library_verdict(conn, problem="p", slug="a", verdict="cite-mathlib",
                           citation="Mathlib.foo")
    _candidate(conn, "b")
    db.set_library_verdict(conn, problem="p", slug="b", verdict="drop")
    # No deduped/classified/migrated → nothing to do.
    assert dispatcher._derive_librarian_work(conn, "p", tmp_path) == (
        None, None)


def test_derive_mixed_prioritises_earliest_stage(tmp_path: Path):
    # A deduped decl alongside a classified one must route to classify
    # first (un-placed kept decls before migrating placed ones).
    conn = _mem()
    _classified(conn, "placed", order=0)
    _deduped(conn, "unplaced")
    work, _ = dispatcher._derive_librarian_work(conn, "p", tmp_path)
    assert work == "classify"


# ---------------------------------------------------------------------
# db.queue_contains + _reenqueue_librarian_if_more
# ---------------------------------------------------------------------

def test_queue_contains(tmp_path: Path):
    conn = _mem()
    assert db.queue_contains(conn, kind="Librarian", target_id="p") is False
    db.enqueue(conn, kind="Librarian", target_id="p",
               target_kind="Problem", priority=0)
    assert db.queue_contains(conn, kind="Librarian", target_id="p") is True
    # Distinct kind / target are not matched.
    assert db.queue_contains(conn, kind="Builder", target_id="p") is False
    assert db.queue_contains(conn, kind="Librarian", target_id="q") is False


def _queue(conn):
    return list(conn.execute(
        "SELECT kind, target_id, target_kind, priority FROM queue"))


def test_reenqueue_when_more_work(tmp_path: Path):
    conn = _mem()
    _deduped(conn, "foo")  # next step is classify
    dispatcher._reenqueue_librarian_if_more(conn, tmp_path, "p")
    rows = _queue(conn)
    assert len(rows) == 1
    assert (rows[0]["kind"], rows[0]["target_id"], rows[0]["target_kind"],
            rows[0]["priority"]) == ("Librarian", "p", "Problem", 0)


def test_reenqueue_no_duplicate(tmp_path: Path):
    conn = _mem()
    _deduped(conn, "foo")
    dispatcher._reenqueue_librarian_if_more(conn, tmp_path, "p")
    dispatcher._reenqueue_librarian_if_more(conn, tmp_path, "p")
    assert len(_queue(conn)) == 1  # guard prevents the second row


def test_reenqueue_stops_when_chain_done(tmp_path: Path):
    conn = _mem()
    _migrated(conn, "foo")
    (tmp_path / "Library").mkdir()
    (tmp_path / "Library" / "INDEX.md").write_text(
        "# Library Index\n\n## p\n\nx\n", encoding="utf-8")
    dispatcher._reenqueue_librarian_if_more(conn, tmp_path, "p")
    assert _queue(conn) == []


def test_reenqueue_migrated_no_index_enqueues_finish(tmp_path: Path):
    # all migrated, no INDEX yet → derive says finish → re-enqueue.
    conn = _mem()
    _migrated(conn, "foo")
    dispatcher._reenqueue_librarian_if_more(conn, tmp_path, "p")
    assert len(_queue(conn)) == 1


# ---------------------------------------------------------------------
# run_finish — INDEX provenance + chain termination
# ---------------------------------------------------------------------

def test_finish_writes_index_provenance(tmp_path: Path):
    conn = _mem()
    _migrated(conn, "foo", order=0)
    _migrated(conn, "bar", order=1)
    r = librarian.run_librarian(
        conn, problem="p", work_kind="finish",
        workspace=tmp_path, pipeline_id="pid-finish")
    assert r.outcome == "success"
    index = tmp_path / "Library" / "INDEX.md"
    assert index.exists()
    text = index.read_text(encoding="utf-8")
    assert "## p" in text
    assert "`foo`" in text and "`bar`" in text
    # The INDEX marker must make derive terminate the chain.
    assert dispatcher._librarian_index_has(tmp_path, "p") is True
    assert dispatcher._derive_librarian_work(conn, "p", tmp_path) == (
        None, None)


def test_finish_is_idempotent(tmp_path: Path):
    conn = _mem()
    _migrated(conn, "foo")
    librarian.run_librarian(conn, problem="p", work_kind="finish",
                            workspace=tmp_path, pipeline_id="pid1")
    librarian.run_librarian(conn, problem="p", work_kind="finish",
                            workspace=tmp_path, pipeline_id="pid2")
    text = (tmp_path / "Library" / "INDEX.md").read_text(encoding="utf-8")
    # Section appears exactly once (no duplicate ## p).
    assert text.count("## p") == 1


def test_finish_two_problems_coexist(tmp_path: Path):
    conn = _mem()
    _migrated(conn, "foo", problem="p")
    _migrated(conn, "baz", problem="q")
    librarian.run_librarian(conn, problem="p", work_kind="finish",
                            workspace=tmp_path, pipeline_id="pid1")
    librarian.run_librarian(conn, problem="q", work_kind="finish",
                            workspace=tmp_path, pipeline_id="pid2")
    text = (tmp_path / "Library" / "INDEX.md").read_text(encoding="utf-8")
    assert "## p" in text and "## q" in text
    assert "`foo`" in text and "`baz`" in text
    # Preamble written once.
    assert text.count("# Library Index") == 1


def test_finish_noop_when_nothing_migrated(tmp_path: Path):
    conn = _mem()
    _deduped(conn, "foo")  # kept but never migrated
    r = librarian.run_librarian(conn, problem="p", work_kind="finish",
                                workspace=tmp_path, pipeline_id="pid")
    assert r.outcome == "success"
    # Nothing harvested → no INDEX written.
    assert not (tmp_path / "Library" / "INDEX.md").exists()


def test_index_has_requires_exact_section(tmp_path: Path):
    (tmp_path / "Library").mkdir()
    (tmp_path / "Library" / "INDEX.md").write_text(
        "# Library Index\n\n## pp\n\nx\n", encoding="utf-8")
    # 'p' must not match the 'pp' section.
    assert dispatcher._librarian_index_has(tmp_path, "p") is False
    assert dispatcher._librarian_index_has(tmp_path, "pp") is True
