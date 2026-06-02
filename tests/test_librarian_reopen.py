"""needs-upstream re-open cascade (librarian._reopen_upstream_cascade +
_parse_needs_upstream + _decline_or_reopen). The Librarian analog of
proof-time return_to_parent: a downstream signals a finalized upstream must
be reshaped → reverse the upstream + its consumer cone to 'classified',
delete their artifacts, record the constraint. Offline; graph monkeypatched.
"""
from __future__ import annotations

import pytest

from Tooling.state import db
from Tooling.pipeline import librarian as lib


@pytest.fixture
def conn():
    c = db.connect(":memory:")
    db.init_schema(c)
    c.execute("INSERT INTO problems (name, manifest_path, created_at, "
              "bootstrap_done) VALUES ('p','',?,1)", (db.now(),))
    c.commit()
    return c


def _placed(conn, slug, target_file, lifecycle="cleaned"):
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


# --- _parse_needs_upstream ---

def test_parse_needs_upstream():
    assert lib._parse_needs_upstream(
        "-- decline: needs-upstream foo_lemma needs the h hypothesis") == (
        "foo_lemma", "needs the h hypothesis")
    assert lib._parse_needs_upstream("-- decline: needs-upstream bar") == (
        "bar", "")
    assert lib._parse_needs_upstream("-- decline: missing-keystone x") is None
    assert lib._parse_needs_upstream("theorem foo := by rfl") is None


# --- _reopen_upstream_cascade ---

def test_reopen_reverses_upstream_and_cone(conn, tmp_path, monkeypatch):
    bar, foo = "Library/P/Bar.lean", "Library/P/Foo.lean"
    _placed(conn, "bar_dep", bar)         # upstream
    _placed(conn, "foo_use", foo)         # imports Bar
    # Foo imports Bar; Main imports Foo (transitive importer)
    graph = {bar: set(), foo: {bar}}
    monkeypatch.setattr(lib, "file_dependency_graph",
                        lambda conn, *, problem, workspace: graph)
    (tmp_path / bar).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / bar).write_text("import Mathlib\n", encoding="utf-8")
    (tmp_path / foo).write_text("import Mathlib\n", encoding="utf-8")

    reopened = lib._reopen_upstream_cascade(
        conn, problem="p", workspace=tmp_path, upstream_slug="bar_dep",
        note="foo_use needs the dropped hypothesis")
    assert set(reopened) == {bar, foo}      # upstream + transitive importer
    # both reverted to 'classified'
    lc = {r["slug"]: r["lifecycle"] for r in db.library_decls_for(conn, "p")}
    assert lc == {"bar_dep": "classified", "foo_use": "classified"}
    # artifacts deleted
    assert not (tmp_path / bar).exists()
    assert not (tmp_path / foo).exists()
    # constraint recorded on the upstream
    note = conn.execute("SELECT reopen_note FROM library_decls WHERE slug="
                        "'bar_dep'").fetchone()[0]
    assert "dropped hypothesis" in note


def test_reopen_unknown_slug_is_noop(conn, tmp_path):
    assert lib._reopen_upstream_cascade(
        conn, problem="p", workspace=tmp_path, upstream_slug="ghost",
        note="x") == []


# --- _decline_or_reopen ---

def test_decline_or_reopen_routes(conn, tmp_path, monkeypatch):
    _placed(conn, "up", "Library/P/Up.lean")
    monkeypatch.setattr(lib, "file_dependency_graph",
                        lambda conn, *, problem, workspace: {"Library/P/Up.lean": set()})
    (tmp_path / "Library" / "P").mkdir(parents=True, exist_ok=True)
    (tmp_path / "Library/P/Up.lean").write_text("import Mathlib\n",
                                                encoding="utf-8")
    r = lib._decline_or_reopen(
        conn, problem="p", workspace=tmp_path,
        patch_text="-- decline: needs-upstream up too weak", stage="bridge")
    assert r.outcome == "failed"
    assert r.failure_reason == "librarian_reopened_upstream"
    assert "up" in r.failure_detail
    # plain decline → agent_declined, no cascade
    r2 = lib._decline_or_reopen(
        conn, problem="p", workspace=tmp_path,
        patch_text="-- decline: not-rederivable", stage="bridge")
    assert r2.failure_reason == "agent_declined"


def test_decline_or_reopen_unknown_slug_fails_loud(conn, tmp_path):
    # needs-upstream names a slug that isn't a declaration in this problem
    # (agent mis-citation) → loud, distinct failure, not a silent cascade no-op.
    r = lib._decline_or_reopen(
        conn, problem="p", workspace=tmp_path,
        patch_text="-- decline: needs-upstream ghost_slug whatever",
        stage="migrate")
    assert r.failure_reason == "librarian_needs_upstream_unresolvable"
    assert "ghost_slug" in r.failure_detail


def test_decline_or_reopen_dropped_slug_fails_loud(conn, tmp_path):
    # X was dedup-merged into Y → dropped, no target_file. needs-upstream X
    # can't be reshaped (X has a replacement Y); fail LOUD surfacing the
    # verdict→replacement, instead of the cascade silently no-op'ing → stall.
    db.upsert_library_decl(conn, problem="p", slug="x_dropped",
                           source_goal_id=None)
    db.set_library_verdict(conn, problem="p", slug="x_dropped",
                           verdict="merge", citation="y_keep")
    conn.commit()
    r = lib._decline_or_reopen(
        conn, problem="p", workspace=tmp_path,
        patch_text="-- decline: needs-upstream x_dropped need a stronger form",
        stage="cleanup")
    assert r.failure_reason == "librarian_needs_upstream_unresolvable"
    assert "x_dropped" in r.failure_detail
    assert "y_keep" in r.failure_detail      # surfaces the replacement
    assert "merge" in r.failure_detail
