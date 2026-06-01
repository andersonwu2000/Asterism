"""Step 4 cleanup — librarian._commit_cleanup + next_cleanup_file + the
cleanup Context.md branch + dispatcher routing. Offline: re-gate and the
unused-var lint are injected, no gateway.

cleanup edits committed Library files in place; the commit re-gates touched
files + importers and rolls back on failure (Gate D no longer applies — the
meaning net is the later bridge Gate B). On pass decls advance to 'cleaned'.
"""
from __future__ import annotations

import pytest

from Tooling.state import db
from Tooling.pipeline import librarian as lib
from Tooling.core import dispatcher


@pytest.fixture
def conn():
    c = db.connect(":memory:")
    db.init_schema(c)
    c.execute("INSERT INTO problems (name, manifest_path, created_at, "
              "bootstrap_done) VALUES ('p','',?,1)", (db.now(),))
    c.commit()
    return c


def _migrated(conn, slug, target_file, *, lifecycle="migrated"):
    g = db.insert_goal(conn, problem="p", slug=slug,
                       lean_path=f"proofs/L_{slug}.lean", statement="True",
                       origin="backward", kind="theorem")
    conn.execute("UPDATE goals SET status='proved' WHERE id=?", (g,))
    db.upsert_library_decl(conn, problem="p", slug=slug, source_goal_id=g)
    db.set_library_verdict(conn, problem="p", slug=slug, verdict="keep")
    db.set_library_classification(conn, problem="p", slug=slug,
                                  target_file=target_file,
                                  target_name=f"Library.P.{slug}", file_order=0)
    db.mark_library_migrated(conn, problem="p", slug=slug)
    if lifecycle == "cleaned":
        db.mark_library_cleaned(conn, problem="p", slug=slug)
    conn.commit()


def _write_lib(workspace, rel, text):
    p = workspace / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


# --- next_cleanup_file ---

def test_next_cleanup_file_picks_migrated(conn):
    _migrated(conn, "a", "Library/P/Foo.lean")
    _migrated(conn, "b", "Library/P/Bar.lean", lifecycle="cleaned")
    assert lib.next_cleanup_file(conn, problem="p") == "Library/P/Foo.lean"


def test_next_cleanup_file_none_when_all_cleaned(conn):
    _migrated(conn, "a", "Library/P/Foo.lean", lifecycle="cleaned")
    assert lib.next_cleanup_file(conn, problem="p") is None


# --- _commit_cleanup ---

def _setup_file(conn, tmp_path, before):
    tf = "Library/P/Foo.lean"
    _migrated(conn, "a", tf)
    _write_lib(tmp_path, tf, before)
    snap = {tf: before}
    return tf, snap


def test_commit_cleanup_pass_marks_cleaned(conn, tmp_path):
    tf, snap = _setup_file(conn, tmp_path, "import Mathlib\n-- old\n")
    _write_lib(tmp_path, tf, "import Mathlib\n/-! # Foo -/\n-- cleaned\n")
    r = lib._commit_cleanup(
        conn, problem="p", workspace=tmp_path, target_file=tf, slugs=["a"],
        snap_before=snap, whitelist=["x"],
        regate=lambda path, text: (True, ""), lint=lambda path: [])
    assert r.outcome == "success", r.failure_detail
    assert db.library_decls_for(conn, "p", lifecycle="cleaned")
    assert not db.library_decls_for(conn, "p", lifecycle="migrated")


def test_commit_cleanup_no_edit_fails(conn, tmp_path):
    tf, snap = _setup_file(conn, tmp_path, "import Mathlib\n")
    # file unchanged → no touch to target
    r = lib._commit_cleanup(
        conn, problem="p", workspace=tmp_path, target_file=tf, slugs=["a"],
        snap_before=snap, whitelist=[],
        regate=lambda path, text: (True, ""), lint=lambda path: [])
    assert r.outcome == "failed"
    assert "no edit" in r.failure_detail


def test_commit_cleanup_regate_fail_rolls_back(conn, tmp_path):
    tf, snap = _setup_file(conn, tmp_path, "import Mathlib\n-- v1\n")
    _write_lib(tmp_path, tf, "import Mathlib\n-- BROKEN\n")
    r = lib._commit_cleanup(
        conn, problem="p", workspace=tmp_path, target_file=tf, slugs=["a"],
        snap_before=snap, whitelist=[],
        regate=lambda path, text: (False, "build error"), lint=lambda path: [])
    assert r.outcome == "failed"
    assert "build error" in r.failure_detail
    # rolled back to the snapshot content
    assert (tmp_path / tf).read_text(encoding="utf-8") == "import Mathlib\n-- v1\n"
    assert db.library_decls_for(conn, "p", lifecycle="migrated")  # not advanced
    assert not db.library_decls_for(conn, "p", lifecycle="cleaned")


def test_commit_cleanup_lint_fail_rolls_back(conn, tmp_path):
    tf, snap = _setup_file(conn, tmp_path, "import Mathlib\n-- v1\n")
    _write_lib(tmp_path, tf, "import Mathlib\n-- edited\n")
    r = lib._commit_cleanup(
        conn, problem="p", workspace=tmp_path, target_file=tf, slugs=["a"],
        snap_before=snap, whitelist=[],
        regate=lambda path, text: (True, ""),
        lint=lambda path: ["unused variable 'h'"])
    assert r.outcome == "failed"
    assert "unused" in r.failure_detail
    assert (tmp_path / tf).read_text(encoding="utf-8") == "import Mathlib\n-- v1\n"
    assert not db.library_decls_for(conn, "p", lifecycle="cleaned")


# --- _regate_touched (shared by cleanup + bridge, G1) ---

def test_regate_touched_detects_and_passes(conn, tmp_path):
    tf = "Library/P/Foo.lean"
    _migrated(conn, "a", tf)
    _write_lib(tmp_path, tf, "import Mathlib\n-- v1\n")
    snap = {tf: "import Mathlib\n-- v0\n"}   # disk differs → touched
    ok, detail, touched = lib._regate_touched(
        conn, problem="p", workspace=tmp_path, snap_before=snap,
        whitelist=[], regate=lambda path, text: (True, ""))
    assert ok and touched == [tf]


def test_regate_touched_no_edit_is_empty(conn, tmp_path):
    tf = "Library/P/Foo.lean"
    _migrated(conn, "a", tf)
    _write_lib(tmp_path, tf, "import Mathlib\n")
    snap = {tf: "import Mathlib\n"}   # unchanged
    ok, detail, touched = lib._regate_touched(
        conn, problem="p", workspace=tmp_path, snap_before=snap,
        whitelist=[], regate=lambda path, text: (False, "should not run"))
    assert ok and touched == []        # nothing touched → no gate, ok


def test_regate_touched_reports_failure(conn, tmp_path):
    tf = "Library/P/Foo.lean"
    _migrated(conn, "a", tf)
    _write_lib(tmp_path, tf, "import Mathlib\n-- broken\n")
    snap = {tf: "import Mathlib\n"}
    ok, detail, touched = lib._regate_touched(
        conn, problem="p", workspace=tmp_path, snap_before=snap,
        whitelist=[], regate=lambda path, text: (False, "build error"))
    assert not ok and "build error" in detail and touched == [tf]


def test_restore_snapshot_reverts(tmp_path):
    tf = "Library/P/Foo.lean"
    _write_lib(tmp_path, tf, "edited\n")
    lib._restore_snapshot(tmp_path, {tf: "original\n"}, [tf])
    assert (tmp_path / tf).read_text(encoding="utf-8") == "original\n"


# --- dispatcher routing ---

def test_derive_migrated_routes_to_cleanup(conn, tmp_path):
    _migrated(conn, "a", "Library/P/Foo.lean")
    work, target = dispatcher._derive_librarian_work(conn, "p", tmp_path)
    assert work == "cleanup"
    assert target == "Library/P/Foo.lean"


def test_derive_cleaned_no_index_routes_to_bridge(conn, tmp_path):
    _migrated(conn, "a", "Library/P/Foo.lean", lifecycle="cleaned")
    assert dispatcher._derive_librarian_work(conn, "p", tmp_path) == (
        "bridge", None)


# --- Context.md cleanup branch ---

def test_cleanup_context_lists_decls_and_conventions(conn, tmp_path):
    tf = "Library/P/Foo.lean"
    _migrated(conn, "a", tf)
    attempts = tmp_path / ".attempts"
    attempts.mkdir()
    ctx = lib.compile_librarian_context(
        conn, problem="p", work_kind="cleanup", attempts_dir=attempts,
        workspace=tmp_path, target_file=tf)
    body = ctx.read_text(encoding="utf-8")
    assert "Clean up" in body
    assert "mathlib_conventions.md" in body
    assert "unusedVariables" in body
    assert "`Library.P.a`" in body
