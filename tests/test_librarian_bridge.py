"""Bridge step (Gate B live) — librarian._commit_bridge + the bridge
Context.md branch. Offline: the axiom prober is injected, no gateway.

Gate B (plan §2, 定海神針) re-derives the original root from the Library; the
bridge file is a throwaway probe (not committed), and INDEX is written only on
a pass — the chain's done-marker.
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


def _migrated(conn, slug, target_name, target_file):
    g = db.insert_goal(conn, problem="p", slug=slug,
                       lean_path=f"proofs/L_{slug}.lean", statement="True",
                       origin="backward", kind="theorem")
    conn.execute("UPDATE goals SET status='proved' WHERE id=?", (g,))
    db.upsert_library_decl(conn, problem="p", slug=slug, source_goal_id=g)
    db.set_library_verdict(conn, problem="p", slug=slug, verdict="keep")
    db.set_library_classification(conn, problem="p", slug=slug,
                                  target_file=target_file,
                                  target_name=target_name, file_order=0)
    db.mark_library_migrated(conn, problem="p", slug=slug)
    conn.commit()


def _root(conn, statement, deps=()):
    g = db.insert_goal(conn, problem="p", slug="main", lean_path="Root.lean",
                       statement=statement, origin="root", kind="theorem")
    conn.execute("UPDATE goals SET status='proved' WHERE id=?", (g,))
    conn.commit()
    return g


_PASS = lambda ws, *, fq_name, module, whitelist: (True, "")
_FAIL = lambda ws, *, fq_name, module, whitelist: (False, "rogue axioms")


def test_commit_bridge_passes_writes_index(conn, tmp_path):
    _migrated(conn, "keystone", "Library.P.Foo.keystone", "Library/P/Foo.lean")
    _root(conn, "True")
    patch = "import Mathlib\n\ntheorem main : True := trivial\n"
    r = lib._commit_bridge(patch, conn=conn, problem="p", workspace=tmp_path,
                           statement="True", whitelist=["a"], prober=_PASS)
    assert r.outcome == "success", r.failure_detail
    index = tmp_path / "Library" / "INDEX.md"
    assert index.exists()
    text = index.read_text(encoding="utf-8")
    assert "Gate B" in text and "PASSED" in text
    assert "`Library.P.Foo.keystone`" in text
    # The bridge probe file itself is NOT left behind.
    leftover = list((tmp_path / "Library").glob("_bridge_probe_*.lean"))
    assert leftover == []


def test_commit_bridge_axiom_fail_no_index(conn, tmp_path):
    _migrated(conn, "keystone", "Library.P.Foo.keystone", "Library/P/Foo.lean")
    _root(conn, "True")
    patch = "import Mathlib\n\ntheorem main : True := trivial\n"
    r = lib._commit_bridge(patch, conn=conn, problem="p", workspace=tmp_path,
                           statement="True", whitelist=["a"], prober=_FAIL)
    assert r.outcome == "failed"
    assert "rogue" in (r.failure_detail or "")
    assert not (tmp_path / "Library" / "INDEX.md").exists()


def test_commit_bridge_statement_pin_rejects_weakened(conn, tmp_path):
    # Bridge proves a DIFFERENT (weaker) statement than the original → the
    # statement-pin in check_root_rederivation rejects it before the prober.
    _migrated(conn, "keystone", "Library.P.Foo.keystone", "Library/P/Foo.lean")
    _root(conn, "True")
    patch = "import Mathlib\n\ntheorem main : True ∨ False := Or.inl trivial\n"
    r = lib._commit_bridge(patch, conn=conn, problem="p", workspace=tmp_path,
                           statement="True", whitelist=["a"], prober=_PASS)
    assert r.outcome == "failed"
    assert not (tmp_path / "Library" / "INDEX.md").exists()


def test_commit_bridge_rejects_problems_import(conn, tmp_path):
    # Import-closure: a bridge importing Problems.* is not Defs-free → reject.
    _migrated(conn, "keystone", "Library.P.Foo.keystone", "Library/P/Foo.lean")
    _root(conn, "True")
    patch = ("import Mathlib\nimport Problems.p.Defs\n\n"
             "theorem main : True := trivial\n")
    r = lib._commit_bridge(patch, conn=conn, problem="p", workspace=tmp_path,
                           statement="True", whitelist=["a"], prober=_PASS)
    assert r.outcome == "failed"
    assert not (tmp_path / "Library" / "INDEX.md").exists()


# --- bridge Context.md branch ---

def test_bridge_context_lists_statement_and_decls(conn, tmp_path):
    _migrated(conn, "keystone", "Library.P.Foo.keystone", "Library/P/Foo.lean")
    _migrated(conn, "helper", "Library.P.Foo.helper", "Library/P/Foo.lean")
    _root(conn, "MyProp x y")
    attempts = tmp_path / ".attempts"
    attempts.mkdir()
    ctx = lib.compile_librarian_context(
        conn, problem="p", work_kind="bridge", attempts_dir=attempts,
        workspace=tmp_path)
    body = ctx.read_text(encoding="utf-8")
    assert "Re-derive the original root" in body
    assert "MyProp x y" in body                       # verbatim statement
    assert "`Library.P.Foo.keystone`" in body         # migrated decls listed
    assert "`Library.P.Foo.helper`" in body
