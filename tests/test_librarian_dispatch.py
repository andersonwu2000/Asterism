"""Librarian dispatcher wiring — P0 phases 3 + 4.

Covers the derive-from-state routing, the race-safe re-enqueue chain,
and INDEX provenance writing (`_write_library_index`, shared by the
terminal bridge step). These are the glue between the verify-hook enqueue
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


def _manifests(**opt_in):
    """ManifestCache stand-in: `problem -> obj with .library`. `dict` supports
    the `in` / `[]` access `_librarian_selfstart_problems` uses. Pass
    `_manifests(p=True)` to mark problem `p` library-opted-in."""
    from types import SimpleNamespace
    return {p: SimpleNamespace(library=v) for p, v in opt_in.items()}


def _proved_root(conn, problem="p", *, integrity_verified=True):
    """Insert a proved root goal so `_librarian_selfstart_problems` sees
    `problem`. `integrity_verified` defaults True (a genuinely-proved root that
    passed `root_integrity_gate`); pass False to simulate a transiently-proved
    root (e.g. a sorryAx fake-proof in the window before the gate rolls it
    back), which must NOT self-start library-ization."""
    _seed_problem(conn, problem)
    gid = db.insert_goal(conn, problem=problem, slug="main",
                         lean_path=f"Problems/{problem}/Root.lean",
                         statement="x", origin="root", status="proved")
    if integrity_verified:
        db.set_integrity_verified(conn, gid)


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
    # v0.4: all files migrated → cleanup-dedup stage (runs before bridge).
    conn = _mem()
    _migrated(conn, "foo")
    assert dispatcher._derive_librarian_work(conn, "p", tmp_path) == (
        "cleanup", None)


def test_derive_cleaned_no_index_is_bridge(tmp_path: Path):
    # cleanup done (all decls cleaned) + no INDEX → bridge Gate B.
    conn = _mem()
    _cleaned(conn, "foo")
    assert dispatcher._derive_librarian_work(conn, "p", tmp_path) == (
        "bridge", None)


def test_derive_cleaned_with_index_is_none(tmp_path: Path):
    # INDEX present (bridge promoted) = done-marker → no further work.
    conn = _mem()
    _cleaned(conn, "foo")
    (tmp_path / "Library").mkdir()
    (tmp_path / "Library" / "INDEX.md").write_text(
        "# Library Index\n\n## p\n\nx\n", encoding="utf-8")
    assert dispatcher._derive_librarian_work(conn, "p", tmp_path) == (
        None, None)


def test_drop_index_section_removes_only_that_problem(tmp_path: Path):
    from Tooling.pipeline import librarian
    text = "# Library Index\n\n## p\n\nx\n\n## q\n\ny\n"
    out = librarian._drop_index_section(text, "p")
    assert "## p" not in out and "## q\n\ny" in out and "# Library Index" in out
    # absent → unchanged; line-exact (won't match `## pp`)
    assert librarian._drop_index_section(text, "pp") == text


def test_reclean_invalidates_stale_index_so_bridge_refires(tmp_path: Path):
    # The stale-INDEX bug: re-cleaning a promoted problem (migrated decls +
    # leftover INDEX) would skip the terminal bridge/Gate B.
    conn = _mem()
    _migrated(conn, "foo")
    (tmp_path / "Library").mkdir()
    idx = tmp_path / "Library" / "INDEX.md"
    idx.write_text("# Library Index\n\n## p\n\nfoo\n", encoding="utf-8")
    # cleanup still runs (migrated present), but INDEX is stale.
    assert dispatcher._derive_librarian_work(conn, "p", tmp_path)[0] == "cleanup"
    dispatcher._librarian_invalidate_index(tmp_path, "p")
    assert "## p" not in idx.read_text(encoding="utf-8")
    # once cleanup finishes (decls cleaned) the now-absent INDEX → bridge re-fires
    # (was wrongly (None, None) before the fix).
    conn.execute("UPDATE library_decls SET lifecycle='cleaned' WHERE problem='p'")
    assert dispatcher._derive_librarian_work(conn, "p", tmp_path) == ("bridge", None)


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
# ready_cleanup_files + file_work_kind cleanup (§13 3c-2 per-file cleanup)
# ---------------------------------------------------------------------

def _migrated_in(conn, slug, target_file, problem="p", order=0):
    """Migrate `slug` into an explicit (possibly shared) file — the cleanup
    phase's per-file unit groups a file's migrated decls together."""
    _classified_in(conn, slug, target_file, problem, order)
    db.mark_library_migrated(conn, problem=problem, slug=slug)


def _drop(conn, slug, citation, problem="p"):
    """Advance a migrated decl to terminal `dropped` (engine drop) — used to
    simulate an earlier cleanup file's drop when testing readiness/ordering."""
    db.set_library_verdict(conn, problem=problem, slug=slug,
                           verdict="drop", citation=citation)


def test_ready_cleanup_files_parallel_independent(tmp_path: Path, monkeypatch):
    # Two independent migrated files → both ready to clean (parallel).
    conn = _mem()
    _migrated_in(conn, "a", "Library/P/Foo.lean")
    _migrated_in(conn, "b", "Library/P/Bar.lean")
    _fake_inventory(monkeypatch, {"a": [], "b": []})
    assert librarian.ready_cleanup_files(
        conn, problem="p", workspace=tmp_path) == [
            ("cleanup", "Library/P/Bar.lean"),
            ("cleanup", "Library/P/Foo.lean")]


def test_ready_cleanup_files_topological_deps_first(tmp_path: Path, monkeypatch):
    # Foo depends on Bar (a uses b). Bottom-up: Bar cleans first; Foo only
    # becomes ready once Bar is DONE (its decls cleaned/dropped).
    conn = _mem()
    _migrated_in(conn, "a", "Library/P/Foo.lean")   # a uses b
    _migrated_in(conn, "b", "Library/P/Bar.lean")
    _fake_inventory(monkeypatch, {"a": ["b"], "b": []})
    assert librarian.ready_cleanup_files(
        conn, problem="p", workspace=tmp_path) == [
            ("cleanup", "Library/P/Bar.lean")]
    db.mark_library_cleaned(conn, problem="p", slug="b")   # Bar done
    assert librarian.ready_cleanup_files(
        conn, problem="p", workspace=tmp_path) == [
            ("cleanup", "Library/P/Foo.lean")]


def test_ready_cleanup_files_dropped_dep_counts_as_done(tmp_path: Path,
                                                        monkeypatch):
    # A dependency file whose only decl was DROPPED is still "done" — its
    # consumer becomes ready (deferred-rewire records the drop for self-apply).
    conn = _mem()
    _migrated_in(conn, "a", "Library/P/Foo.lean")   # a uses b
    _migrated_in(conn, "b", "Library/P/Bar.lean")
    _fake_inventory(monkeypatch, {"a": ["b"], "b": []})
    _drop(conn, "b", citation="Mathlib.thing")      # Bar fully dropped → done
    assert librarian.ready_cleanup_files(
        conn, problem="p", workspace=tmp_path) == [
            ("cleanup", "Library/P/Foo.lean")]


def test_ready_cleanup_files_skips_inflight(tmp_path: Path, monkeypatch):
    conn = _mem()
    _migrated_in(conn, "a", "Library/P/Foo.lean")
    _migrated_in(conn, "b", "Library/P/Bar.lean")
    _fake_inventory(monkeypatch, {"a": [], "b": []})
    assert librarian.ready_cleanup_files(
        conn, problem="p", workspace=tmp_path,
        in_flight={"Library/P/Foo.lean"}) == [("cleanup", "Library/P/Bar.lean")]


def test_ready_cleanup_files_none_when_all_done(tmp_path: Path):
    conn = _mem()
    _cleaned(conn, "a")
    assert librarian.ready_cleanup_files(
        conn, problem="p", workspace=tmp_path) == []


def test_file_work_kind_cleanup_for_migrated(tmp_path: Path):
    # A file with migrated (un-cleaned) decls → 'cleanup'; classified → migrate.
    conn = _mem()
    _migrated_in(conn, "a", "Library/P/Foo.lean")
    assert librarian.file_work_kind(
        conn, problem="p", target_file="Library/P/Foo.lean") == "cleanup"


def test_file_work_kind_migrate_takes_priority(tmp_path: Path):
    # Mixed file (still has a classified decl) → migrate before cleanup.
    conn = _mem()
    _migrated_in(conn, "a", "Library/P/Foo.lean", order=0)
    _classified_in(conn, "b", "Library/P/Foo.lean", order=1)
    assert librarian.file_work_kind(
        conn, problem="p", target_file="Library/P/Foo.lean") == "migrate"


def test_file_work_kind_none_when_cleaned(tmp_path: Path):
    conn = _mem()
    _cleaned(conn, "a")
    assert librarian.file_work_kind(
        conn, problem="p", target_file="Library/P/a.lean") is None


def test_file_dependency_graph_cleanup_keeps_dropped_edge(tmp_path: Path,
                                                          monkeypatch):
    # The cleanup-phase graph spans migrated/cleaned/DROPPED so a consumer's
    # import edge to a dropped dependency survives (stable ordering, §13).
    conn = _mem()
    _migrated_in(conn, "a", "Library/P/Foo.lean")   # a uses b
    _migrated_in(conn, "b", "Library/P/Bar.lean")
    _fake_inventory(monkeypatch, {"a": ["b"], "b": []})
    _drop(conn, "b", citation="Mathlib.thing")
    # default lifecycles (classified/migrated) drop b → edge lost
    assert librarian.file_dependency_graph(
        conn, problem="p", workspace=tmp_path)["Library/P/Foo.lean"] == set()
    # cleanup lifecycles keep b → edge preserved
    g = librarian.file_dependency_graph(
        conn, problem="p", workspace=tmp_path,
        lifecycles=("migrated", "cleaned", "dropped"))
    assert g["Library/P/Foo.lean"] == {"Library/P/Bar.lean"}


# ---------------------------------------------------------------------
# db.queue_contains
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


def test_librarian_refill_serial_phase_enqueues_one(tmp_path: Path):
    # #92 — a serial phase (here: classify) enqueues ONE plain `problem` row.
    conn = _mem()
    _deduped(conn, "foo")  # next step is classify
    dispatcher._librarian_refill(conn, tmp_path, set(), _manifests(), fail_counts={})
    rows = _queue(conn)
    assert len(rows) == 1
    assert (rows[0]["kind"], rows[0]["target_id"], rows[0]["target_kind"],
            rows[0]["priority"]) == ("Librarian", "p", "Problem", 0)


def test_librarian_refill_serial_no_duplicate(tmp_path: Path):
    conn = _mem()
    _deduped(conn, "foo")
    dispatcher._librarian_refill(conn, tmp_path, set(), _manifests(), fail_counts={})
    dispatcher._librarian_refill(conn, tmp_path, set(), _manifests(), fail_counts={})
    assert len(_queue(conn)) == 1  # queue_contains guard


def test_librarian_refill_stops_when_chain_done(tmp_path: Path):
    conn = _mem()
    _cleaned(conn, "foo")
    (tmp_path / "Library").mkdir()
    (tmp_path / "Library" / "INDEX.md").write_text(
        "# Library Index\n\n## p\n\nx\n", encoding="utf-8")
    dispatcher._librarian_refill(conn, tmp_path, set(), _manifests(), fail_counts={})
    assert _queue(conn) == []


def test_librarian_refill_migrate_phase_parallel_per_file(tmp_path: Path):
    # #92 — two INDEPENDENT classified files both enqueue as per-file migrate
    # units (parallel), each target_id = `problem\x1ffile`.
    conn = _mem()
    _classified(conn, "foo", order=0)   # Library/P/foo.lean
    _classified(conn, "bar", order=1)   # Library/P/bar.lean
    dispatcher._librarian_refill(conn, tmp_path, set(), _manifests(), fail_counts={})
    tids = sorted(r["target_id"] for r in _queue(conn))
    assert tids == sorted([
        dispatcher._lib_encode("p", "Library/P/bar.lean"),
        dispatcher._lib_encode("p", "Library/P/foo.lean")])


def test_librarian_refill_skips_inflight_and_queued(tmp_path: Path):
    conn = _mem()
    _classified(conn, "foo", order=0)
    _classified(conn, "bar", order=1)
    foo_tid = dispatcher._lib_encode("p", "Library/P/foo.lean")
    running = {(foo_tid, "Librarian", None)}    # foo already in flight
    dispatcher._librarian_refill(conn, tmp_path, running, _manifests(), fail_counts={})
    assert [r["target_id"] for r in _queue(conn)] == [
        dispatcher._lib_encode("p", "Library/P/bar.lean")]
    # second refill: bar now queued → no duplicate, foo still in-flight
    dispatcher._librarian_refill(conn, tmp_path, running, _manifests(), fail_counts={})
    assert len(_queue(conn)) == 1


def test_librarian_refill_migrated_enqueues_cleanup_per_file(tmp_path: Path):
    # §13 3c-2: a wholly-migrated problem (no classified left) → cleanup, a
    # PER-FILE phase → one `problem\x1ffile` row per ready file (not a serial
    # plain `problem` row). Two independent files enqueue in parallel.
    conn = _mem()
    _migrated(conn, "foo", order=0)   # Library/P/foo.lean
    _migrated(conn, "bar", order=1)   # Library/P/bar.lean
    dispatcher._librarian_refill(conn, tmp_path, set(), _manifests(), fail_counts={})
    tids = sorted(r["target_id"] for r in _queue(conn))
    assert tids == sorted([
        dispatcher._lib_encode("p", "Library/P/bar.lean"),
        dispatcher._lib_encode("p", "Library/P/foo.lean")])


def test_librarian_refill_cleanup_skips_inflight_file(tmp_path: Path):
    # A cleanup file already in flight is not re-enqueued; its independent
    # sibling still is (per-file parallelism, like migrate).
    conn = _mem()
    _migrated(conn, "foo", order=0)
    _migrated(conn, "bar", order=1)
    foo_tid = dispatcher._lib_encode("p", "Library/P/foo.lean")
    running = {(foo_tid, "Librarian", None)}
    dispatcher._librarian_refill(conn, tmp_path, running, _manifests(), fail_counts={})
    assert [r["target_id"] for r in _queue(conn)] == [
        dispatcher._lib_encode("p", "Library/P/bar.lean")]


def test_librarian_refill_cleaned_enqueues_bridge_serial(tmp_path: Path):
    # Once every file is cleaned (no migrated left) the chain advances to the
    # bridge Gate B — a whole-problem SERIAL step → one plain `problem` row.
    conn = _mem()
    _cleaned(conn, "foo")
    dispatcher._librarian_refill(conn, tmp_path, set(), _manifests(), fail_counts={})
    rows = _queue(conn)
    assert len(rows) == 1
    assert (rows[0]["kind"], rows[0]["target_id"]) == ("Librarian", "p")


def test_librarian_refill_skips_stalled_file(tmp_path: Path):
    conn = _mem()
    _classified(conn, "foo", order=0)
    tid = dispatcher._lib_encode("p", "Library/P/foo.lean")
    fc = {tid: dispatcher.LIBRARIAN_MAX_CHAIN_RETRIES + 1}   # stalled unit
    dispatcher._librarian_refill(conn, tmp_path, set(), _manifests(), fail_counts=fc)
    assert _queue(conn) == []   # stalled file is not re-enqueued


# ---------------------------------------------------------------------
# #92 Bug A/B — pending return + self-start of opted-in proved problems
# ---------------------------------------------------------------------

def test_librarian_refill_returns_pending_when_work(tmp_path: Path):
    # Live work (a serial step here) → pending True so the exit gate holds.
    conn = _mem()
    _deduped(conn, "foo")  # classify pending
    pending = dispatcher._librarian_refill(
        conn, tmp_path, set(), _manifests(), fail_counts={})
    assert pending is True


def test_librarian_refill_not_pending_when_drained(tmp_path: Path):
    # Chain done (cleaned + INDEX) → no work → not pending → daemon may exit.
    conn = _mem()
    _cleaned(conn, "foo")
    (tmp_path / "Library").mkdir()
    (tmp_path / "Library" / "INDEX.md").write_text(
        "# Library Index\n\n## p\n\nx\n", encoding="utf-8")
    pending = dispatcher._librarian_refill(
        conn, tmp_path, set(), _manifests(), fail_counts={})
    assert pending is False
    assert _queue(conn) == []


def test_librarian_refill_not_pending_when_fully_stalled(tmp_path: Path):
    # Only remaining work is a stalled unit → NOT pending (daemon exits for
    # the operator instead of looping forever).
    conn = _mem()
    _classified(conn, "foo", order=0)
    tid = dispatcher._lib_encode("p", "Library/P/foo.lean")
    fc = {tid: dispatcher.LIBRARIAN_MAX_CHAIN_RETRIES + 1}
    pending = dispatcher._librarian_refill(
        conn, tmp_path, set(), _manifests(), fail_counts=fc)
    assert pending is False


def test_librarian_refill_selfstart_opted_in_proved(tmp_path: Path):
    # Bug B — opted-in (library:true) proved problem with NO library_decls and
    # no INDEX self-starts dedup (no verify-hook / manual seed needed).
    conn = _mem()
    _proved_root(conn, "p")
    pending = dispatcher._librarian_refill(
        conn, tmp_path, set(), _manifests(p=True), fail_counts={})
    assert pending is True
    rows = _queue(conn)
    assert len(rows) == 1
    assert (rows[0]["kind"], rows[0]["target_id"]) == ("Librarian", "p")


def test_librarian_refill_no_selfstart_until_integrity_verified(tmp_path: Path):
    # A transiently-proved-but-not-integrity-verified root (e.g. a sorryAx
    # fake-proof before root_integrity_gate rolls it back) must NOT self-start
    # library-ization: classify on still-stubbed proofs sizes files from the
    # wrong line counts (P13 PerBumpStokes oversize TOCTOU). Fires only at iv=1.
    conn = _mem()
    _proved_root(conn, "p", integrity_verified=False)
    pending = dispatcher._librarian_refill(
        conn, tmp_path, set(), _manifests(p=True), fail_counts={})
    assert pending is False
    assert _queue(conn) == []
    # once root_integrity_gate sets iv=1 (clean #print axioms) → self-starts
    gid = conn.execute(
        "SELECT id FROM goals WHERE problem='p' AND origin='root'").fetchone()[0]
    db.set_integrity_verified(conn, gid)
    pending = dispatcher._librarian_refill(
        conn, tmp_path, set(), _manifests(p=True), fail_counts={})
    assert pending is True
    rows = _queue(conn)
    assert len(rows) == 1 and rows[0]["kind"] == "Librarian"


def test_librarian_refill_no_selfstart_when_not_opted_in(tmp_path: Path):
    # A proved problem WITHOUT library:true is never auto-Library-ized.
    conn = _mem()
    _proved_root(conn, "p")
    pending = dispatcher._librarian_refill(
        conn, tmp_path, set(), _manifests(p=False), fail_counts={})
    assert pending is False
    assert _queue(conn) == []


def test_librarian_refill_no_selfstart_when_index_present(tmp_path: Path):
    # Opted-in + proved but INDEX already written (chain done) → no self-start.
    conn = _mem()
    _proved_root(conn, "p")
    (tmp_path / "Library").mkdir()
    (tmp_path / "Library" / "INDEX.md").write_text(
        "# Library Index\n\n## p\n\nx\n", encoding="utf-8")
    pending = dispatcher._librarian_refill(
        conn, tmp_path, set(), _manifests(p=True), fail_counts={})
    assert pending is False
    assert _queue(conn) == []


def test_advance_chain_success_clears_count_no_enqueue(tmp_path: Path):
    # #92 — _advance only tracks fail counts now; re-enqueue is the refill's job.
    conn = _mem()
    tid = dispatcher._lib_encode("p", "Library/P/foo.lean")
    fc = {tid: 2}
    dispatcher._advance_librarian_chain(
        conn, tmp_path, tid, outcome="success", reason="", fail_counts=fc)
    assert tid not in fc            # counter cleared on success
    assert _queue(conn) == []       # advance never enqueues


def test_advance_chain_failure_counts_no_enqueue(tmp_path: Path):
    conn = _mem()
    tid = dispatcher._lib_encode("p", "Library/P/foo.lean")
    fc: dict = {}
    for attempt in (1, 2, 3):
        dispatcher._advance_librarian_chain(
            conn, tmp_path, tid, outcome="failed", reason="boom",
            fail_counts=fc)
        assert fc[tid] == attempt   # per-unit count climbs
        assert _queue(conn) == []   # advance never enqueues (refill does)


def test_advance_chain_fail_count_persists_across_restart(tmp_path: Path):
    # #92 B#3 — the cap must survive a daemon restart: _advance write-throughs to
    # the DB, and the dict the daemon rebuilds at startup sees the stuck count.
    conn = _mem()
    tid = dispatcher._lib_encode("p", "Library/P/foo.lean")
    fc: dict = {}
    for _ in (1, 2):
        dispatcher._advance_librarian_chain(
            conn, tmp_path, tid, outcome="failed", reason="boom", fail_counts=fc)
    # simulate restart: fresh dict rebuilt from DB (what run() does post-init_schema)
    assert db.librarian_fail_counts_all(conn) == {tid: 2}      # survived
    # a later success clears it from the DB too (not just the in-memory dict)
    dispatcher._advance_librarian_chain(
        conn, tmp_path, tid, outcome="success", reason="", fail_counts=fc)
    assert db.librarian_fail_counts_all(conn) == {}


# ---------------------------------------------------------------------
# INDEX provenance — _write_library_index (live; shared by the bridge step)
# ---------------------------------------------------------------------

_GATE_B_PASS = "Gate B (root re-derivation): PASSED."


def test_index_write_then_derive_terminates(tmp_path: Path):
    conn = _mem()
    _cleaned(conn, "foo", order=0)        # post-cleanup state (bridge writes INDEX)
    _cleaned(conn, "bar", order=1)
    librarian._write_library_index(
        conn, problem="p", workspace=tmp_path, gate_b_line=_GATE_B_PASS)
    index = tmp_path / "Library" / "INDEX.md"
    assert index.exists()
    text = index.read_text(encoding="utf-8")
    assert "## p" in text
    assert "`foo`" in text and "`bar`" in text
    # The INDEX marker must make derive terminate the chain.
    assert dispatcher._librarian_index_has(tmp_path, "p") is True
    assert dispatcher._derive_librarian_work(conn, "p", tmp_path) == (
        None, None)


def test_index_write_idempotent(tmp_path: Path):
    conn = _mem()
    _migrated(conn, "foo")
    for _ in range(2):
        librarian._write_library_index(
            conn, problem="p", workspace=tmp_path, gate_b_line=_GATE_B_PASS)
    text = (tmp_path / "Library" / "INDEX.md").read_text(encoding="utf-8")
    # Section appears exactly once (no duplicate ## p).
    assert text.count("## p") == 1


def test_index_two_problems_coexist(tmp_path: Path):
    conn = _mem()
    _migrated(conn, "foo", problem="p")
    _migrated(conn, "baz", problem="q")
    for prob in ("p", "q"):
        librarian._write_library_index(
            conn, problem=prob, workspace=tmp_path, gate_b_line=_GATE_B_PASS)
    text = (tmp_path / "Library" / "INDEX.md").read_text(encoding="utf-8")
    assert "## p" in text and "## q" in text
    assert "`foo`" in text and "`baz`" in text
    # Preamble written once.
    assert text.count("# Library Index") == 1


def test_index_has_requires_exact_section(tmp_path: Path):
    (tmp_path / "Library").mkdir()
    (tmp_path / "Library" / "INDEX.md").write_text(
        "# Library Index\n\n## pp\n\nx\n", encoding="utf-8")
    # 'p' must not match the 'pp' section.
    assert dispatcher._librarian_index_has(tmp_path, "p") is False
    assert dispatcher._librarian_index_has(tmp_path, "pp") is True


def test_advance_chain_file_busy_not_counted(tmp_path: Path):
    # Same-path migrate contention is transient — the loser's fast retries
    # must not burn LIBRARIAN_MAX_CHAIN_RETRIES while the winner (minutes)
    # holds the path (live cap-burn, 2026-06-11).
    conn = _mem()
    tid = dispatcher._lib_encode("p", "Library/P/foo.lean")
    fc: dict = {}
    for _ in range(5):
        dispatcher._advance_librarian_chain(
            conn, tmp_path, tid, outcome="failed",
            reason="librarian_file_busy", fail_counts=fc)
    assert tid not in fc                          # never counted
    assert db.librarian_fail_counts_all(conn) == {}


def test_advance_chain_stall_surfaces_failure_detail(tmp_path: Path, capsys):
    # The STALL line must surface the real error (failure_detail), read from
    # dead_attempts by pipeline_id — Librarian records the detail under
    # target_id=0, so it can't be found by problem/file (was hand-dig-only).
    conn = _mem()
    tid = dispatcher._lib_encode("p", "Library/P/foo.lean")
    pid = "pl-stall-1"
    db.record_pipeline(                       # FK: dead_attempts → pipelines(id)
        conn, pipeline_id=pid, kind="Librarian", target_id="p",
        target_kind="Problem", status="failed", outcome="failed",
        started_at=db.now())
    db.record_dead_attempt(
        conn, target_id=0, target_kind="Problem", pipeline_id=pid,
        failure_reason="schema_violation",
        failure_detail="naming_violation: `Foo.bar` must be snake_case\n2nd line")
    fc = {tid: dispatcher.LIBRARIAN_MAX_CHAIN_RETRIES}   # next fail → STALL
    dispatcher._advance_librarian_chain(
        conn, tmp_path, tid, outcome="failed", reason="schema_violation",
        fail_counts=fc, pipeline_id=pid)
    out = capsys.readouterr().out
    assert "STALLED" in out
    assert "naming_violation" in out          # detail surfaced inline
    assert "2nd line" not in out              # only the detail's first line


def test_advance_chain_stall_without_pipeline_id_is_safe(tmp_path: Path, capsys):
    # No pipeline_id (or no matching dead_attempt) → STALL still prints, just
    # without the detail tail; must never raise.
    conn = _mem()
    tid = dispatcher._lib_encode("p", "Library/P/foo.lean")
    fc = {tid: dispatcher.LIBRARIAN_MAX_CHAIN_RETRIES}
    dispatcher._advance_librarian_chain(
        conn, tmp_path, tid, outcome="failed", reason="boom", fail_counts=fc)
    out = capsys.readouterr().out
    assert "STALLED" in out and "boom" in out


def test_clear_librarian_fail_counts_for_problem_scopes_to_problem():
    # A fresh classify clears a problem's stall counts (new attempt). Drops the
    # plain `problem` serial row + every `problem\x1f<file>` per-file row, and
    # leaves OTHER problems' counts intact — even a problem whose name shares a
    # prefix (the match is exact, not a LIKE wildcard).
    conn = _mem()
    db.set_librarian_fail_count(conn, target_id="p", n=2)
    db.set_librarian_fail_count(conn, target_id="p\x1fLibrary/P/A.lean", n=3)
    db.set_librarian_fail_count(conn, target_id="p\x1fLibrary/P/B.lean", n=1)
    db.set_librarian_fail_count(conn, target_id="p2\x1fLibrary/Q/C.lean", n=3)
    n = db.clear_librarian_fail_counts_for_problem(conn, "p")
    assert n == 3
    remaining = db.librarian_fail_counts_all(conn)
    assert remaining == {"p2\x1fLibrary/Q/C.lean": 3}


def test_commit_classify_clears_stale_fail_counts(tmp_path, monkeypatch):
    # End-to-end: a stale per-file stall count from a prior ingestion is
    # cleared when classify re-lays-out the problem, so a reverted+re-ingested
    # problem doesn't inherit a STALL that skips the file forever.
    conn = _mem()
    _seed_problem(conn, "p")
    _deduped(conn, "foo")                       # a kept decl awaiting classify
    db.set_librarian_fail_count(
        conn, target_id="p\x1fLibrary/P/Foo.lean", n=3)   # stale cap
    # Minimal ClassifyPlan: one file, one decl. Avoid the usage-graph read by
    # stubbing it (no proof files on disk in this unit test).
    monkeypatch.setattr(
        "Tooling.quality.librarian.inventory.usage_graph",
        lambda *a, **k: {})
    from Tooling.pipeline.librarian import ClassifyPlan, ClassifyFile
    plan = ClassifyPlan(files=[ClassifyFile(
        path="Library/P/Foo.lean", decls=["foo"])])
    librarian.commit_classify(conn, "p", plan, tmp_path)
    assert db.librarian_fail_counts_all(conn) == {}      # stale cap cleared
