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


def _cleaned(conn, slug, problem="p", order=0):
    _migrated(conn, slug, problem, order)
    db.mark_library_cleaned(conn, problem=problem, slug=slug)


# ---------------------------------------------------------------------
# _derive_librarian_work — pure state → (work_kind, target)
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


def test_derive_classified_is_migrate_ready_file(tmp_path: Path):
    conn = _mem()
    # migrate's target is a FILE now (per-file is the parallel unit). With
    # no cross-file deps, the first ready file is the first by path.
    _classified(conn, "bbb", order=1)   # → Library/P/bbb.lean
    _classified(conn, "aaa", order=0)   # → Library/P/aaa.lean
    work, target = dispatcher._derive_librarian_work(conn, "p", tmp_path)
    assert work == "migrate"
    assert target == "Library/P/aaa.lean"


def test_derive_migrated_is_cleanup(tmp_path: Path):
    # A migrated (not-yet-cleaned) decl → Step 4 cleanup on its file.
    conn = _mem()
    _migrated(conn, "foo")
    assert dispatcher._derive_librarian_work(conn, "p", tmp_path) == (
        "cleanup", "Library/P/foo.lean")


def test_derive_cleaned_no_index_is_bridge(tmp_path: Path):
    # All cleaned, INDEX not yet written → the terminal agentic Gate B step
    # (bridge re-derives the root, then writes INDEX = done-marker).
    conn = _mem()
    _cleaned(conn, "foo")
    assert dispatcher._derive_librarian_work(conn, "p", tmp_path) == (
        "bridge", None)


def test_derive_cleaned_with_index_is_none(tmp_path: Path):
    conn = _mem()
    _cleaned(conn, "foo")
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
# file_dependency_graph + next_migrate_file (GAP 1/2 — per-file migrate)
# ---------------------------------------------------------------------

def _classified_in(conn, slug, target_file, problem="p", order=0):
    """Classify `slug` into an explicit (possibly shared) file — per-file
    migrate places several decls in one file."""
    _deduped(conn, slug, problem)
    db.set_library_classification(
        conn, problem=problem, slug=slug, target_file=target_file,
        target_name=None, file_order=order)


def _fake_inventory(monkeypatch, deps_by_slug):
    """Patch usage_graph so the file DAG is driven by an explicit slug→uses
    map instead of on-disk proof files. The cross-file graph now follows the
    USAGE DAG (proof-term citations), not decomposition deps."""
    from Tooling.quality.librarian import inventory as inv_mod
    monkeypatch.setattr(
        inv_mod, "usage_graph",
        lambda ws, prob, slugs, **k: {
            s: set(deps_by_slug.get(s, [])) for s in slugs})


def test_next_migrate_file_groups_decls(tmp_path: Path):
    conn = _mem()
    _classified_in(conn, "a", "Library/P/Foo.lean", order=0)
    _classified_in(conn, "b", "Library/P/Foo.lean", order=1)
    assert librarian.next_migrate_file(
        conn, problem="p", workspace=tmp_path) == "Library/P/Foo.lean"


def test_file_dependency_graph_cross_file(tmp_path: Path, monkeypatch):
    conn = _mem()
    _classified_in(conn, "a", "Library/P/Foo.lean")   # a uses b
    _classified_in(conn, "b", "Library/P/Bar.lean")
    _fake_inventory(monkeypatch, {"a": ["b"], "b": []})
    g = librarian.file_dependency_graph(conn, problem="p", workspace=tmp_path)
    assert g == {"Library/P/Foo.lean": {"Library/P/Bar.lean"},
                 "Library/P/Bar.lean": set()}


def test_next_migrate_file_topological(tmp_path: Path, monkeypatch):
    conn = _mem()
    # Foo depends on Bar; Bar must migrate first even though Foo sorts
    # earlier by path.
    _classified_in(conn, "a", "Library/P/Foo.lean")   # a uses b
    _classified_in(conn, "b", "Library/P/Bar.lean")
    _fake_inventory(monkeypatch, {"a": ["b"], "b": []})
    assert librarian.next_migrate_file(
        conn, problem="p", workspace=tmp_path) == "Library/P/Bar.lean"
    db.mark_library_migrated(conn, problem="p", slug="b")
    assert librarian.next_migrate_file(
        conn, problem="p", workspace=tmp_path) == "Library/P/Foo.lean"


def test_next_migrate_file_none_when_no_classified(tmp_path: Path):
    conn = _mem()
    _migrated(conn, "a")
    assert librarian.next_migrate_file(
        conn, problem="p", workspace=tmp_path) is None


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
    _cleaned(conn, "foo")
    (tmp_path / "Library").mkdir()
    (tmp_path / "Library" / "INDEX.md").write_text(
        "# Library Index\n\n## p\n\nx\n", encoding="utf-8")
    dispatcher._reenqueue_librarian_if_more(conn, tmp_path, "p")
    assert _queue(conn) == []


def test_reenqueue_migrated_no_index_enqueues_more(tmp_path: Path):
    # migrated, no INDEX yet → derive says cleanup → re-enqueue.
    conn = _mem()
    _migrated(conn, "foo")
    dispatcher._reenqueue_librarian_if_more(conn, tmp_path, "p")
    assert len(_queue(conn)) == 1


# ---------------------------------------------------------------------
# run_finish — INDEX provenance + chain termination
# ---------------------------------------------------------------------

def test_finish_writes_index_provenance(tmp_path: Path):
    conn = _mem()
    _cleaned(conn, "foo", order=0)
    _cleaned(conn, "bar", order=1)
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
