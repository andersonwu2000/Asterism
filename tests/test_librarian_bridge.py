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


# --- v0.3 mechanical bridge (no agent) ---

from Tooling.pipeline import PipelineResult as _PR


def _migrate_existing(conn, slug, target_name, target_file, goal_id):
    """Add a migrated library_decl for an ALREADY-inserted goal (avoids the
    goals UNIQUE(problem,slug) clash when the decl IS the root `main`)."""
    db.upsert_library_decl(conn, problem="p", slug=slug, source_goal_id=goal_id)
    db.set_library_verdict(conn, problem="p", slug=slug, verdict="keep")
    db.set_library_classification(conn, problem="p", slug=slug,
                                  target_file=target_file,
                                  target_name=target_name, file_order=0)
    db.mark_library_migrated(conn, problem="p", slug=slug)
    conn.commit()


def test_bridge_probe_text_cites_migrated_main(conn, tmp_path):
    # v0.3 (plan §2/§3): the mechanical Gate B probe imports every migrated
    # module, opens every migrated namespace, and re-derives the original
    # `main` by citing its migrated form.
    root_g = _root(conn, "True")
    _migrate_existing(conn, "main", "Library.P.Foo.main",
                      "Library/P/Foo.lean", root_g)
    _migrated(conn, "lem", "Library.P.Bar.lem", "Library/P/Bar.lean")
    migrated = lib._harvested_decls(conn, "p")
    probe = lib._bridge_probe_text(conn, problem="p", statement="True",
                                   migrated=migrated)
    assert "import Library.P.Foo" in probe
    assert "import Library.P.Bar" in probe
    assert "open Library.P.Foo" in probe
    assert "theorem main : True := by exact Library.P.Foo.main" in probe


def _mock_lake_ok(monkeypatch):
    # Gate B now rebuilds the cleaned modules' oleans before the probe; stub the
    # real `lake build` (no lake project under tmp_path) so the test reaches the
    # probe/commit step.
    import Tooling.pipeline._lake as _lake
    monkeypatch.setattr(_lake, "lake_build_modules", lambda ws, mods: (True, ""))


def test_run_bridge_pass_writes_index(conn, tmp_path, monkeypatch):
    root_g = _root(conn, "True")
    _migrate_existing(conn, "main", "Library.P.Foo.main",
                      "Library/P/Foo.lean", root_g)
    _mock_lake_ok(monkeypatch)
    monkeypatch.setattr(lib, "_commit_bridge",
                        lambda *a, **k: _PR(outcome="success"))
    r = lib._run_bridge(conn, problem="p", workspace=tmp_path, pipeline_id="pid")
    assert r.outcome == "success"


def test_run_bridge_fail_is_not_mechanical(conn, tmp_path, monkeypatch):
    # Cleaned Library builds but the citation doesn't typecheck → operator-flag.
    root_g = _root(conn, "True")
    _migrate_existing(conn, "main", "Library.P.Foo.main",
                      "Library/P/Foo.lean", root_g)
    _mock_lake_ok(monkeypatch)
    monkeypatch.setattr(lib, "_commit_bridge", lambda *a, **k: _PR(
        outcome="failed", failure_reason="librarian_gate_failed",
        failure_detail="type mismatch"))
    r = lib._run_bridge(conn, problem="p", workspace=tmp_path, pipeline_id="pid")
    assert r.outcome == "failed"
    assert r.failure_reason == "librarian_bridge_not_mechanical"
    assert "type mismatch" in r.failure_detail        # real error surfaced


def test_run_bridge_cleaned_build_failed_is_distinct(conn, tmp_path, monkeypatch):
    # Cleaned Library doesn't build (a cleanup bug, e.g. dangling cross-file ref)
    # → distinct reason + real lake error, NOT relabelled "load-bearing Defs".
    # The probe is never reached.
    root_g = _root(conn, "True")
    _migrate_existing(conn, "main", "Library.P.Foo.main",
                      "Library/P/Foo.lean", root_g)
    import Tooling.pipeline._lake as _lake
    monkeypatch.setattr(_lake, "lake_build_modules",
                        lambda ws, mods: (False, "unknown identifier 'dropped_lemma'"))
    monkeypatch.setattr(lib, "_commit_bridge", lambda *a, **k: pytest.fail(
        "_commit_bridge must not run when the cleaned Library fails to build"))
    r = lib._run_bridge(conn, problem="p", workspace=tmp_path, pipeline_id="pid")
    assert r.outcome == "failed"
    assert r.failure_reason == "librarian_cleaned_build_failed"
    assert "unknown identifier 'dropped_lemma'" in r.failure_detail
