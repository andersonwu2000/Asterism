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
    c.execute("INSERT INTO problems (name, created_at, "
              "bootstrap_done) VALUES ('p',?,1)", (db.now(),))
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
    # v18: the done-marker + Gate B note live in the DB, not INDEX.md.
    from Tooling.state import db as _db
    assert _db.problem_library_bridged(conn, "p") is True
    note = conn.execute("SELECT library_bridge_note FROM problems"
                        " WHERE name='p'").fetchone()[0]
    assert "Gate B" in note and "PASSED" in note
    assert [r2["slug"] for r2 in _db.bridged_library_index(conn)["p"]] == [
        "keystone"]
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
    from Tooling.state import db as _db
    assert _db.problem_library_bridged(conn, "p") is False


def test_commit_bridge_statement_pin_rejects_weakened(conn, tmp_path):
    # Bridge proves a DIFFERENT (weaker) statement than the original → the
    # statement-pin in check_root_rederivation rejects it before the prober.
    _migrated(conn, "keystone", "Library.P.Foo.keystone", "Library/P/Foo.lean")
    _root(conn, "True")
    patch = "import Mathlib\n\ntheorem main : True ∨ False := Or.inl trivial\n"
    r = lib._commit_bridge(patch, conn=conn, problem="p", workspace=tmp_path,
                           statement="True", whitelist=["a"], prober=_PASS)
    assert r.outcome == "failed"
    from Tooling.state import db as _db
    assert _db.problem_library_bridged(conn, "p") is False


def test_commit_bridge_rejects_problems_import(conn, tmp_path):
    # Import-closure: a bridge importing Problems.* is not Defs-free → reject.
    _migrated(conn, "keystone", "Library.P.Foo.keystone", "Library/P/Foo.lean")
    _root(conn, "True")
    patch = ("import Mathlib\nimport Problems.p.Defs\n\n"
             "theorem main : True := trivial\n")
    r = lib._commit_bridge(patch, conn=conn, problem="p", workspace=tmp_path,
                           statement="True", whitelist=["a"], prober=_PASS)
    assert r.outcome == "failed"
    from Tooling.state import db as _db
    assert _db.problem_library_bridged(conn, "p") is False


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


def test_bridge_probe_text_replays_defs_opens(conn, tmp_path):
    # A statement is AUTHORED under Defs.lean's file-level opens — scoped
    # notation (`open scoped Manifold` → `𝓡∂`/`∞`) doesn't even PARSE without
    # them, and the probe then fails as a false
    # `librarian_bridge_not_mechanical` (stokes 2026-06-11). The probe must
    # replay them, like every other proof-file author (inject_defs_opens).
    pd = tmp_path / "Problems" / "p"
    pd.mkdir(parents=True, exist_ok=True)
    (pd / "Defs.lean").write_text(
        "import Mathlib\n\nopen scoped Manifold Bundle ContDiff\n"
        "open MeasureTheory\nopen Foo in\nexample : True := trivial\n",
        encoding="utf-8")
    root_g = _root(conn, "True")
    _migrate_existing(conn, "main", "Library.P.Foo.main",
                      "Library/P/Foo.lean", root_g)
    migrated = lib._harvested_decls(conn, "p")
    probe = lib._bridge_probe_text(conn, problem="p", statement="True",
                                   migrated=migrated, workspace=tmp_path)
    assert "open scoped Manifold Bundle ContDiff" in probe
    assert "open MeasureTheory" in probe
    assert "open Foo" not in probe          # `open X in` is decl-scoped — excluded
    # opens land between the imports and the theorem
    assert probe.index("import Library.P.Foo") \
        < probe.index("open scoped Manifold") < probe.index("theorem main")
    # without a workspace the probe is unchanged (back-compat)
    bare = lib._bridge_probe_text(conn, problem="p", statement="True",
                                  migrated=migrated)
    assert "Manifold" not in bare


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
    monkeypatch.setattr(lib.bridge, "_commit_bridge",
                        lambda *a, **k: _PR(outcome="success"))
    r = lib._run_bridge(conn, problem="p", workspace=tmp_path, pipeline_id="pid")
    assert r.outcome == "success"


def test_run_bridge_fail_is_not_mechanical(conn, tmp_path, monkeypatch):
    # Cleaned Library builds but the citation doesn't typecheck → operator-flag.
    root_g = _root(conn, "True")
    _migrate_existing(conn, "main", "Library.P.Foo.main",
                      "Library/P/Foo.lean", root_g)
    _mock_lake_ok(monkeypatch)
    monkeypatch.setattr(lib.bridge, "_commit_bridge", lambda *a, **k: _PR(
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
    monkeypatch.setattr(lib.bridge, "_commit_bridge", lambda *a, **k: pytest.fail(
        "_commit_bridge must not run when the cleaned Library fails to build"))
    r = lib._run_bridge(conn, problem="p", workspace=tmp_path, pipeline_id="pid")
    assert r.outcome == "failed"
    assert r.failure_reason == "librarian_cleaned_build_failed"
    assert "unknown identifier 'dropped_lemma'" in r.failure_detail


def _deliverable_setup(conn, tmp_path):
    """A proved root + one migrated decl marked deliverable, its Library file
    on disk (the deliverable gate reads the FINAL on-disk text)."""
    _root(conn, "True")
    _migrated(conn, "foo", "Library.P.Foo.foo", "Library/P/Foo.lean")
    conn.execute("UPDATE goals SET is_deliverable=1 "
                 "WHERE problem='p' AND slug='foo'")
    conn.commit()
    fp = tmp_path / "Library" / "P" / "Foo.lean"
    fp.parent.mkdir(parents=True, exist_ok=True)
    fp.write_text("import Mathlib\ntheorem foo : True := trivial\n",
                  encoding="utf-8")


def test_run_bridge_deliverable_axiom_gate_blocks_index(conn, tmp_path,
                                                        monkeypatch):
    # deliverable branch: "builds" alone never inspects the kernel axiom
    # graph — the per-file axiom gate (post cite_drop, the chain's last
    # rewrite) must block the INDEX on a rogue axiom.
    from Tooling.pipeline.librarian import gate as _g
    _deliverable_setup(conn, tmp_path)
    _mock_lake_ok(monkeypatch)
    monkeypatch.setattr(_g, "migrate_commit_gate",
                        lambda *a, **k: _g.MigrateResult(
                            False, "rogue axioms: ['Lean.ofReduceBool']"))
    r = lib._run_bridge(conn, problem="p", workspace=tmp_path,
                        pipeline_id="pid", whitelist=["propext"])
    assert r.outcome == "failed"
    assert r.failure_reason == "librarian_axiom_violation"
    assert "rogue axioms" in r.failure_detail
    assert not (tmp_path / "Library" / "INDEX.md").exists()


def test_run_bridge_deliverable_axiom_gate_passes_writes_index(conn, tmp_path,
                                                               monkeypatch):
    from Tooling.pipeline.librarian import gate as _g
    _deliverable_setup(conn, tmp_path)
    _mock_lake_ok(monkeypatch)
    calls: list = []

    def _fake(text, path, *, whitelist=None, probe_verifier=None,
              workspace=None):
        calls.append({"text": text, "whitelist": whitelist})
        return _g.MigrateResult(True, "")
    monkeypatch.setattr(_g, "migrate_commit_gate", _fake)
    r = lib._run_bridge(conn, problem="p", workspace=tmp_path,
                        pipeline_id="pid", whitelist=["propext"])
    assert r.outcome == "success"
    assert calls and calls[0]["whitelist"] == ["propext"]
    assert "theorem foo" in calls[0]["text"]         # final on-disk text
    from Tooling.state import db as _db
    assert _db.problem_library_bridged(conn, "p") is True
    note = conn.execute("SELECT library_bridge_note FROM problems"
                        " WHERE name='p'").fetchone()[0]
    assert "per-decl axiom check" in note


def test_run_bridge_pure_nl_no_root_takes_deliverable_branch(conn, tmp_path,
                                                             monkeypatch):
    """Phase 6 regression (Analysis.metric_projection 2026-07-04): the
    `librarian_no_root` early-exit used to sit ABOVE the deliverable
    branch, so a pure-NL problem (no root goal at all) STALLED the bridge
    before its deliverables could take over. The root fetch now lives in
    the classic path only."""
    from Tooling.pipeline.librarian import gate as _g
    # deliverable setup WITHOUT any root goal
    _migrated(conn, "foo", "Library.P.Foo.foo", "Library/P/Foo.lean")
    conn.execute("UPDATE goals SET is_deliverable=1 "
                 "WHERE problem='p' AND slug='foo'")
    conn.commit()
    fp = tmp_path / "Library" / "P" / "Foo.lean"
    fp.parent.mkdir(parents=True, exist_ok=True)
    fp.write_text("import Mathlib\ntheorem foo : True := trivial\n",
                  encoding="utf-8")
    _mock_lake_ok(monkeypatch)
    monkeypatch.setattr(_g, "migrate_commit_gate",
                        lambda *a, **k: _g.MigrateResult(True, ""))
    r = lib._run_bridge(conn, problem="p", workspace=tmp_path,
                        pipeline_id="pid", whitelist=["propext"])
    assert r.outcome == "success", r.failure_detail
    from Tooling.state import db as _db
    assert _db.problem_library_bridged(conn, "p") is True


def test_run_bridge_deliverable_no_whitelist_skips_gate(conn, tmp_path,
                                                        monkeypatch):
    # Contract pin: whitelist=None (unit tests / legacy callers) keeps the old
    # builds-only behavior; the dispatcher always passes a whitelist.
    from Tooling.pipeline.librarian import gate as _g
    _deliverable_setup(conn, tmp_path)
    _mock_lake_ok(monkeypatch)
    monkeypatch.setattr(_g, "migrate_commit_gate",
                        lambda *a, **k: pytest.fail(
                            "deliverable axiom gate must not run without "
                            "a whitelist"))
    r = lib._run_bridge(conn, problem="p", workspace=tmp_path,
                        pipeline_id="pid")
    assert r.outcome == "success"


def test_run_librarian_bridge_dispatches_without_prompt(conn, tmp_path,
                                                        monkeypatch) -> None:
    # bridge is a mechanical (no-agent, no-prompt) probe — run_librarian must
    # dispatch it BEFORE the prompt-existence guard, so the deleted bridge.md
    # never trips librarian_missing_prompt.
    sentinel = _PR(outcome="success")
    monkeypatch.setattr(lib.bridge, "_run_bridge", lambda *a, **k: sentinel)
    r = lib.run_librarian(conn, problem="p", work_kind="bridge",
                          workspace=tmp_path, pipeline_id="x")
    assert r is sentinel
