"""Librarian pipeline stage A — pure parse + verify + commit for the
classify work kind (no gateway / no LLM)."""
from __future__ import annotations

import json

import pytest

from Tooling.state import db
from Tooling.pipeline import librarian as lib


# ---------------------------------------------------------------------
# parse_classify
# ---------------------------------------------------------------------

def test_parse_classify_ok():
    js = json.dumps({"files": [
        {"path": "Library/Algebra/Foo.lean", "imports": [], "decls": ["a"]},
        {"path": "Library/Algebra/Bar.lean",
         "imports": ["Library.Algebra.Foo"], "decls": ["b", "c"]},
    ]})
    plan, err = lib.parse_classify(js)
    assert err == ""
    assert len(plan.files) == 2
    assert plan.files[1].decls == ["b", "c"]


def test_parse_classify_missing_files():
    plan, err = lib.parse_classify('{"foo": 1}')
    assert plan is None and "files" in err


def test_parse_classify_empty_decls():
    plan, err = lib.parse_classify(
        '{"files":[{"path":"Library/X.lean","decls":[]}]}')
    assert plan is None and "decls" in err


# ---------------------------------------------------------------------
# verify_classify
# ---------------------------------------------------------------------

def _plan(files):
    return lib.ClassifyPlan([lib.ClassifyFile(**f) for f in files])


def test_verify_classify_ok():
    plan = _plan([
        {"path": "Library/A/Foo.lean", "imports": [], "decls": ["a"]},
        {"path": "Library/A/Bar.lean",
         "imports": ["Library.A.Foo"], "decls": ["b"]},
    ])
    assert lib.verify_classify(plan, {"a", "b"}) == ""


def test_verify_classify_missing_decl():
    plan = _plan([{"path": "Library/A/Foo.lean", "imports": [], "decls": ["a"]}])
    assert "not placed" in lib.verify_classify(plan, {"a", "b"})


def test_verify_classify_stray_decl():
    plan = _plan([{"path": "Library/A/Foo.lean", "imports": [],
                   "decls": ["a", "z"]}])
    assert "non-kept" in lib.verify_classify(plan, {"a"})


def test_verify_classify_decl_twice():
    plan = _plan([
        {"path": "Library/A/Foo.lean", "imports": [], "decls": ["a"]},
        {"path": "Library/A/Bar.lean", "imports": [], "decls": ["a"]},
    ])
    assert "more than one file" in lib.verify_classify(plan, {"a"})


def test_verify_classify_nonlibrary_import():
    plan = _plan([{"path": "Library/A/Foo.lean",
                   "imports": ["Problems.p.Defs"], "decls": ["a"]}])
    assert "not a Library module" in lib.verify_classify(plan, {"a"})


def test_verify_classify_import_cycle():
    plan = _plan([
        {"path": "Library/A/Foo.lean",
         "imports": ["Library.A.Bar"], "decls": ["a"]},
        {"path": "Library/A/Bar.lean",
         "imports": ["Library.A.Foo"], "decls": ["b"]},
    ])
    assert "cycle" in lib.verify_classify(plan, {"a", "b"})


def test_verify_classify_file_size_budget():
    # The giant-file gate (BT Equidecomp, 2026-06-11): a planned file whose
    # decls sum over CLASSIFY_FILE_LINE_BUDGET is rejected with a split
    # instruction; under budget passes; no decl_lines → no size check.
    plan = _plan([{"path": "Library/A/Big.lean", "imports": [],
                   "decls": ["a", "b"]}])
    over = {"a": lib.CLASSIFY_FILE_LINE_BUDGET, "b": 1}
    err = lib.verify_classify(plan, {"a", "b"}, decl_lines=over)
    assert "Library/A/Big.lean" in err and "split" in err
    under = {"a": 500, "b": 500}
    assert lib.verify_classify(plan, {"a", "b"}, decl_lines=under) == ""
    assert lib.verify_classify(plan, {"a", "b"}) == ""   # back-compat


def test_decl_line_counts_reads_proof_files(tmp_path):
    proofs = tmp_path / "Problems" / "p" / "proofs"
    proofs.mkdir(parents=True)
    (proofs / "L_foo.lean").write_text("import Mathlib\nx\ny\n", encoding="utf-8")
    out = lib._decl_line_counts(tmp_path, "p", ["foo", "ghost"])
    assert out == {"foo": 3, "ghost": 0}    # missing file counts 0


# ---------------------------------------------------------------------
# commit (into library_decls)
# ---------------------------------------------------------------------

@pytest.fixture
def conn():
    c = db.connect(":memory:")
    db.init_schema(c)
    c.execute("INSERT INTO problems (name, manifest_path, created_at, "
              "bootstrap_done) VALUES ('p','',?,1)", (db.now(),))
    c.commit()
    return c


def test_commit_classify(conn, tmp_path):
    for s in ("a", "b"):
        db.upsert_library_decl(conn, problem="p", slug=s, source_goal_id=None)
        db.set_library_verdict(conn, problem="p", slug=s, verdict="keep")
    plan = lib.ClassifyPlan([
        lib.ClassifyFile("Library/A/Foo.lean", [], ["a", "b"]),
    ])
    lib.commit_classify(conn, "p", plan, tmp_path)
    classified = db.library_decls_for(conn, "p", lifecycle="classified")
    by_slug = {r["slug"]: r for r in classified}
    assert set(by_slug) == {"a", "b"}
    assert by_slug["a"]["target_file"] == "Library/A/Foo.lean"
    assert by_slug["a"]["file_order"] == 0
    assert by_slug["b"]["file_order"] == 1


# ---------------------------------------------------------------------
# cleanup stage — _run_cleanup (engine monkeypatched; no lake)
# ---------------------------------------------------------------------

def _seed_migrated(conn, slug, fqn, *, problem="p", target_file="Library/P/F.lean"):
    db.upsert_library_decl(conn, problem=problem, slug=slug, source_goal_id=None)
    db.set_library_verdict(conn, problem=problem, slug=slug, verdict="keep")
    db.set_library_classification(conn, problem=problem, slug=slug,
                                  target_file=target_file, target_name=fqn,
                                  file_order=0)
    db.mark_library_migrated(conn, problem=problem, slug=slug)


def _patch_engine(monkeypatch, result):
    from Tooling.quality.librarian import dedup as _dedup
    monkeypatch.setattr(_dedup, "run_staged_cleanup",
                        lambda ws, prob, **kw: result)


def test_run_cleanup_drops_and_cleans(conn, tmp_path, monkeypatch):
    _seed_migrated(conn, "foo", "Library.P.F.foo")
    _seed_migrated(conn, "bar", "Library.P.F.bar")
    _patch_engine(monkeypatch, {
        "dropped": {"Library.P.F.foo": "Library.P.F.bar"},
        "merged": set(), "near": [], "skipped": [], "bridged": {}})
    res = lib._run_cleanup(conn, problem="p", workspace=tmp_path)
    assert res.outcome == "success"
    life = {r["slug"]: r["lifecycle"] for r in db.library_decls_for(conn, "p")}
    assert life["foo"] == "dropped"        # engine-dropped → terminal dropped
    assert life["bar"] == "cleaned"        # survivor → cleaned
    # no `migrated` left → derive won't loop back to cleanup
    assert not db.library_decls_for(conn, "p", lifecycle="migrated")


def test_run_cleanup_noop_still_cleans_all(conn, tmp_path, monkeypatch):
    # zero drops must still advance every migrated decl → no infinite cleanup loop
    _seed_migrated(conn, "foo", "Library.P.F.foo")
    _patch_engine(monkeypatch, {"dropped": {}, "merged": set(), "near": [],
                                "skipped": [], "bridged": {}})
    lib._run_cleanup(conn, problem="p", workspace=tmp_path)
    life = {r["slug"]: r["lifecycle"] for r in db.library_decls_for(conn, "p")}
    assert life["foo"] == "cleaned"
    assert not db.library_decls_for(conn, "p", lifecycle="migrated")


# ---------------------------------------------------------------------
# cleanup stage — per-file path (§13 3c-2 dispatcher unit)
# ---------------------------------------------------------------------

def _patch_engine_file(monkeypatch, result, captured=None):
    from Tooling.quality.librarian import dedup as _dedup

    def _fake(ws, prob, target_file, **kw):
        if captured is not None:
            captured.update(target_file=target_file, **kw)
        return result
    monkeypatch.setattr(_dedup, "run_staged_cleanup_file", _fake)


def test_run_cleanup_per_file_only_advances_that_file(conn, tmp_path, monkeypatch):
    # Per-file unit advances ONLY its own file's decls; other files untouched.
    _seed_migrated(conn, "foo", "Library.P.F.foo", target_file="Library/P/F.lean")
    _seed_migrated(conn, "baz", "Library.P.G.baz", target_file="Library/P/G.lean")
    cap: dict = {}
    _patch_engine_file(monkeypatch, {"dropped": {}, "merged": set(),
                                     "bridged": {}, "near": [], "failed": []}, cap)
    res = lib._run_cleanup(conn, problem="p", workspace=tmp_path,
                           target_file="Library/P/F.lean")
    assert res.outcome == "success"
    life = {r["slug"]: r["lifecycle"] for r in db.library_decls_for(conn, "p")}
    assert life["foo"] == "cleaned"     # this file advanced
    assert life["baz"] == "migrated"    # other file untouched
    assert cap["target_file"] == "Library/P/F.lean"


def test_run_cleanup_per_file_drop_records_citation(conn, tmp_path, monkeypatch):
    _seed_migrated(conn, "foo", "Library.P.F.foo", target_file="Library/P/F.lean")
    _seed_migrated(conn, "bar", "Library.P.F.bar", target_file="Library/P/F.lean")
    _patch_engine_file(monkeypatch, {
        "dropped": {"Library.P.F.foo": "Library.P.F.bar"},
        "merged": set(), "bridged": {}, "near": [], "failed": []})
    lib._run_cleanup(conn, problem="p", workspace=tmp_path,
                     target_file="Library/P/F.lean")
    by_slug = {r["slug"]: r for r in db.library_decls_for(conn, "p")}
    assert by_slug["foo"]["lifecycle"] == "dropped"
    assert by_slug["foo"]["citation"] == "Library.P.F.bar"
    assert by_slug["bar"]["lifecycle"] == "cleaned"


def test_run_cleanup_per_file_reads_prior_renames_from_db(conn, tmp_path,
                                                          monkeypatch):
    # An earlier (dependency) file already dropped `gone`→`keep`; cleaning a
    # later consumer file must surface that drop as `prior_renames` so the
    # consumer self-applies the rewire (deferred-rewire, §13).
    _seed_migrated(conn, "keep", "Library.P.G.keep", target_file="Library/P/G.lean")
    db.mark_library_cleaned(conn, problem="p", slug="keep")    # survivor, done
    _seed_migrated(conn, "gone", "Library.P.D.gone", target_file="Library/P/D.lean")
    db.set_library_verdict(conn, problem="p", slug="gone", verdict="drop",
                           citation="Library.P.G.keep")        # earlier drop
    _seed_migrated(conn, "user", "Library.P.U.user", target_file="Library/P/U.lean")
    cap: dict = {}
    _patch_engine_file(monkeypatch, {"dropped": {}, "merged": set(),
                                     "bridged": {}, "near": [], "failed": []}, cap)
    lib._run_cleanup(conn, problem="p", workspace=tmp_path,
                     target_file="Library/P/U.lean")
    assert cap["prior_renames"] == {"Library.P.D.gone": "Library.P.G.keep"}


def _patch_olean_refresh(monkeypatch, captured=None):
    """Stub the renamed-file olean rebuild (no lake in unit tests)."""
    from Tooling.pipeline import _lake

    def _build(ws, modules):
        if captured is not None:
            captured.append(list(modules))
        return True, ""
    monkeypatch.setattr(_lake, "lake_build_modules", _build)


def test_run_cleanup_per_file_records_rename(conn, tmp_path, monkeypatch):
    # A P4 rename of a kept survivor: target_name → new fqn, renamed_from → old,
    # decl still advances to cleaned, and the file's olean is refreshed.
    _seed_migrated(conn, "foo", "Library.P.F.foo", target_file="Library/P/F.lean")
    _patch_engine_file(monkeypatch, {
        "dropped": {}, "merged": set(), "bridged": {}, "near": [], "failed": [],
        "renamed": {"Library.P.F.foo": "Library.P.F.foo_aligned"}})
    built: list = []
    _patch_olean_refresh(monkeypatch, built)
    lib._run_cleanup(conn, problem="p", workspace=tmp_path,
                     target_file="Library/P/F.lean")
    row = {r["slug"]: r for r in db.library_decls_for(conn, "p")}["foo"]
    assert row["lifecycle"] == "cleaned"
    assert row["target_name"] == "Library.P.F.foo_aligned"
    assert row["renamed_from"] == "Library.P.F.foo"
    assert built == [["Library.P.F"]]            # olean refreshed for this module


def test_run_cleanup_per_file_imports_min_refreshes_olean(conn, tmp_path,
                                                          monkeypatch):
    # decide's import swap changes the file without renaming anything — the
    # olean is just as stale (consumers import this module), so imports_min
    # alone must trigger the refresh.
    _seed_migrated(conn, "foo", "Library.P.F.foo", target_file="Library/P/F.lean")
    _patch_engine_file(monkeypatch, {
        "dropped": {}, "merged": set(), "bridged": {}, "near": [], "failed": [],
        "renamed": {}, "imports_min": True})
    built: list = []
    _patch_olean_refresh(monkeypatch, built)
    lib._run_cleanup(conn, problem="p", workspace=tmp_path,
                     target_file="Library/P/F.lean")
    row = {r["slug"]: r for r in db.library_decls_for(conn, "p")}["foo"]
    assert row["lifecycle"] == "cleaned"
    assert row["renamed_from"] is None           # no rename recorded
    assert built == [["Library.P.F"]]            # but olean still refreshed


def test_run_cleanup_per_file_audited_refreshes_olean(conn, tmp_path,
                                                      monkeypatch):
    # audit's free rewrite changes the file without renames/imports — the olean
    # is stale all the same, so audited alone must trigger the refresh.
    _seed_migrated(conn, "foo", "Library.P.F.foo", target_file="Library/P/F.lean")
    _patch_engine_file(monkeypatch, {
        "dropped": {}, "merged": set(), "bridged": {}, "near": [], "failed": [],
        "renamed": {}, "imports_min": False, "audited": True})
    built: list = []
    _patch_olean_refresh(monkeypatch, built)
    lib._run_cleanup(conn, problem="p", workspace=tmp_path,
                     target_file="Library/P/F.lean")
    assert built == [["Library.P.F"]]


def test_run_cleanup_per_file_rename_olean_fail_is_loud(conn, tmp_path, monkeypatch):
    # The renamed-file olean rebuild is load-bearing (consumers gate against the
    # new names). `lake_build_modules` returns (False, out) on failure — it does
    # NOT raise — so a failure must be SURFACED, not silently dropped (the old
    # try/except: pass left a stale olean → downstream silent-stall).
    _seed_migrated(conn, "foo", "Library.P.F.foo", target_file="Library/P/F.lean")
    _patch_engine_file(monkeypatch, {
        "dropped": {}, "merged": set(), "bridged": {}, "near": [], "failed": [],
        "renamed": {"Library.P.F.foo": "Library.P.F.foo_aligned"}})
    from Tooling.pipeline import _lake
    monkeypatch.setattr(_lake, "lake_build_modules",
                        lambda ws, modules: (False, "error: unknown identifier"))
    res = lib._run_cleanup(conn, problem="p", workspace=tmp_path,
                           target_file="Library/P/F.lean")
    assert res.outcome == "failed"
    assert res.failure_reason == "librarian_cleaned_build_failed"


def test_run_cleanup_per_file_prior_renames_includes_renames(conn, tmp_path,
                                                             monkeypatch):
    # An earlier file renamed `old`→`new` (kept survivor). A later consumer file
    # must surface that as a prior_rename so it self-applies the token rewrite.
    _seed_migrated(conn, "k", "Library.P.G.new", target_file="Library/P/G.lean")
    db.set_library_renamed(conn, problem="p", slug="k",
                           old_fqn="Library.P.G.old", new_fqn="Library.P.G.new")
    db.mark_library_cleaned(conn, problem="p", slug="k")
    _seed_migrated(conn, "user", "Library.P.U.user", target_file="Library/P/U.lean")
    cap: dict = {}
    _patch_engine_file(monkeypatch, {"dropped": {}, "merged": set(),
                                     "bridged": {}, "near": [], "failed": []}, cap)
    lib._run_cleanup(conn, problem="p", workspace=tmp_path,
                     target_file="Library/P/U.lean")
    assert cap["prior_renames"] == {"Library.P.G.old": "Library.P.G.new"}


# ---------------------------------------------------------------------
# Stage B — migrate_commit_gate (injectable build_verifier, no gateway)
# ---------------------------------------------------------------------

from pathlib import Path as _P


def _ok_probe(_text):
    return (True, "", {})


def _fail_probe(msg):
    def _v(_text):
        return (False, msg, {})
    return _v


def test_migrate_gate_clean_passes():
    patch = ("import Mathlib\nimport Library.A.Foo\n"
             "namespace Library.A\n"
             "theorem t : True := trivial\nend Library.A\n")
    r = lib.migrate_commit_gate(patch, _P("Library/A/Bar.lean"),
                                probe_verifier=_ok_probe)
    assert r.ok, r.detail


def test_migrate_gate_rejects_problems_import():
    patch = ("import Mathlib\nimport Problems.p.Defs\n"
             "theorem t : True := trivial\n")
    r = lib.migrate_commit_gate(patch, _P("Library/A/Bar.lean"),
                                probe_verifier=_ok_probe)
    assert not r.ok and "Problems.p.Defs" in r.detail


def test_migrate_gate_rejects_sorry():
    patch = ("import Mathlib\n"
             "theorem t : True := by sorry\n")
    r = lib.migrate_commit_gate(patch, _P("Library/A/Bar.lean"),
                                probe_verifier=_ok_probe)
    assert not r.ok and "sorry" in r.detail


def test_migrate_gate_rejects_build_failure():
    patch = ("import Mathlib\n"
             "theorem t : True := trivial\n")
    r = lib.migrate_commit_gate(
        patch, _P("Library/A/Bar.lean"),
        probe_verifier=_fail_probe("unknown identifier 'foo'"))
    assert not r.ok and "build failed" in r.detail
    assert "foo" in r.detail


def test_migrate_gate_closure_checked_before_build():
    """A Problems import is caught even if the build would pass — the
    cheap text gate runs first."""
    patch = "import Problems.x.Defs\ntheorem t : True := trivial\n"
    called = {"n": 0}
    def _spy(_t):
        called["n"] += 1
        return (True, "", {})
    r = lib.migrate_commit_gate(patch, _P("Library/A/Bar.lean"),
                                probe_verifier=_spy)
    assert not r.ok
    assert called["n"] == 0  # build never reached


# ---------------------------------------------------------------------
# extract_decl_fq_name + per-file axiom check (whitelist + axiom_verifier)
# ---------------------------------------------------------------------

def test_extract_decl_fq_name_with_namespace():
    patch = ("import Mathlib\nnamespace Library.A.Foo\n"
             "theorem bar (h : True) : True := h\nend Library.A.Foo\n")
    assert lib.extract_decl_fq_name(patch) == "Library.A.Foo.bar"


def test_extract_decl_fq_name_no_namespace():
    assert lib.extract_decl_fq_name(
        "import Mathlib\ndef baz : Nat := 0\n") == "baz"


def test_extract_decl_fq_name_skips_modifiers():
    patch = ("namespace Library.A\nnoncomputable def q : Nat := 0\n"
             "end Library.A\n")
    assert lib.extract_decl_fq_name(patch) == "Library.A.q"


def test_extract_decl_fq_name_none_when_anonymous():
    # An anonymous `instance : … :=` has no name to print axioms for.
    patch = "import Mathlib\ninstance : Inhabited Nat := ⟨0⟩\n"
    assert lib.extract_decl_fq_name(patch) is None


def test_extract_decls_multiple_in_order():
    patch = ("import Mathlib\nnamespace Library.A\n"
             "/-- d -/\ntheorem t1 : True := trivial\n"
             "/-- d -/\ndef d2 : Nat := 0\n"
             "end Library.A\n")
    decls = lib.extract_decls(patch)
    assert [(d.kind, d.fq_name) for d in decls] == [
        ("theorem", "Library.A.t1"), ("def", "Library.A.d2")]


def test_extract_decls_namespace_pop():
    # `end <ns>` pops the namespace so a later section qualifies correctly.
    patch = ("namespace A\ndef x : Nat := 0\nend A\n"
             "namespace B\ndef y : Nat := 0\nend B\n")
    assert [d.fq_name for d in lib.extract_decls(patch)] == ["A.x", "B.y"]


def test_migrate_gate_axiom_clean_passes():
    patch = ("import Mathlib\nnamespace Library.A\n"
             "theorem t : True := trivial\nend Library.A\n")
    r = lib.migrate_commit_gate(
        patch, _P("Library/A/Bar.lean"), whitelist=["propext"],
        probe_verifier=lambda _t: (True, "", {"Library.A.t": {"propext"}}))
    assert r.ok, r.detail


def test_migrate_gate_rejects_rogue_axiom():
    """build passes but the decl's transitive axiom set escapes the
    whitelist (e.g. sorryAx from an imported stub) → reject."""
    patch = ("import Mathlib\nnamespace Library.A\n"
             "theorem t : True := trivial\nend Library.A\n")
    r = lib.migrate_commit_gate(
        patch, _P("Library/A/Bar.lean"), whitelist=["propext"],
        probe_verifier=lambda _t: (True, "", {"Library.A.t": {"sorryAx"}}))
    assert not r.ok
    assert "axiom check failed" in r.detail and "sorryAx" in r.detail


def test_migrate_gate_axiom_missing_report_rejected():
    """whitelist set, build passes, but a decl has no `#print axioms` report
    in the probe output (probe omitted / name unresolved) → reject rather
    than silently treating it as axiom-free (keeps the invariant honest)."""
    patch = ("import Mathlib\nnamespace Library.A\n"
             "theorem t : True := trivial\nend Library.A\n")
    r = lib.migrate_commit_gate(
        patch, _P("Library/A/Bar.lean"), whitelist=["propext"],
        probe_verifier=lambda _t: (True, "", {}))   # no report for Library.A.t
    assert not r.ok
    assert "axiom check failed" in r.detail and "no `#print axioms`" in r.detail


def test_migrate_gate_probe_carries_print_axioms_when_whitelisted():
    """With a whitelist, the probe text the verifier sees must carry a
    `#print axioms <fq>` per decl; without one, it must NOT (build-only)."""
    patch = ("import Mathlib\nnamespace Library.A\n"
             "theorem t : True := trivial\nend Library.A\n")
    seen = {}
    def _spy(text):
        seen["text"] = text
        return (True, "", {"Library.A.t": {"propext"}})
    r = lib.migrate_commit_gate(
        patch, _P("Library/A/Bar.lean"), whitelist=["propext"],
        probe_verifier=_spy)
    assert r.ok, r.detail
    assert "#print axioms Library.A.t" in seen["text"]


def test_migrate_gate_axiom_skipped_without_whitelist():
    """whitelist=None (the unit-test default) skips the axiom check — the
    probe runs build-only, with no `#print axioms` lines appended."""
    patch = ("import Mathlib\nnamespace Library.A\n"
             "theorem t : True := trivial\nend Library.A\n")
    seen = {}
    def _spy(text):
        seen["text"] = text
        return (True, "", {})
    r = lib.migrate_commit_gate(
        patch, _P("Library/A/Bar.lean"), probe_verifier=_spy)
    assert r.ok
    assert "#print axioms" not in seen["text"]


def test_migrate_gate_axiom_unextractable_name_rejected():
    """whitelist set but the patch has no named decl → the gate fails
    rather than silently skipping the axiom check (keeps the per-file
    invariant honest)."""
    patch = "import Mathlib\ninstance : Inhabited Nat := ⟨0⟩\n"
    r = lib.migrate_commit_gate(
        patch, _P("Library/A/Bar.lean"), whitelist=["propext"],
        probe_verifier=_ok_probe)
    assert not r.ok


# ---------------------------------------------------------------------
# batched axiom probe helpers (_axiom_probe_text / _parse_axiom_diags)
# ---------------------------------------------------------------------

def test_axiom_probe_text_appends_one_print_per_decl():
    patch = "namespace L\ntheorem a : True := trivial\nend L\n"
    out = lib._axiom_probe_text(patch, ["L.a", "L.b"])
    assert out.startswith(patch)
    assert "#print axioms L.a" in out and "#print axioms L.b" in out


def test_axiom_probe_text_empty_names_unchanged():
    patch = "namespace L\ntheorem a : True := trivial\nend L\n"
    assert lib._axiom_probe_text(patch, []) == patch
    assert lib._axiom_probe_text(patch, [None]) == patch


def test_parse_axiom_diags_depends_and_none():
    diags = [
        {"severity": "info",
         "message": "'L.a' depends on axioms: [propext, Classical.choice]"},
        {"severity": "info", "message": "'L.b' does not depend on any axioms"},
        # non-info diagnostics ignored (warnings, errors)
        {"severity": "warning", "message": "'L.c' depends on axioms: [sorryAx]"},
    ]
    out = lib._parse_axiom_diags(diags)
    assert out == {"L.a": {"propext", "Classical.choice"}, "L.b": set()}


def test_parse_axiom_diags_multiline_axiom_list():
    # Lean may wrap a long axiom list across lines; DOTALL must still parse it.
    diags = [{"severity": "info",
              "message": "'L.a' depends on axioms: [propext,\n Quot.sound,\n"
                         " Classical.choice]"}]
    out = lib._parse_axiom_diags(diags)
    assert out == {"L.a": {"propext", "Quot.sound", "Classical.choice"}}


# ---------------------------------------------------------------------
# Stage C — compile_librarian_context
# ---------------------------------------------------------------------

def _goal_with_stmt(conn, slug, stmt):
    return db.insert_goal(conn, problem="p", slug=slug,
                          lean_path=f"proofs/L_{slug}.lean",
                          statement=stmt, origin="backward", kind="theorem")


def test_context_classify_only_kept(conn, tmp_path):
    root = db.insert_goal(conn, problem="p", slug="main",
                          lean_path="Problems/p/Root.lean",
                          statement="M", origin="root", kind="theorem")
    conn.execute("UPDATE goals SET status='proved' WHERE id=?", (root,))
    for s in ("keep_me", "drop_me"):
        g = _goal_with_stmt(conn, s, f"{s}_stmt")
        conn.execute("UPDATE goals SET status='proved' WHERE id=?", (g,))
    conn.commit()
    for s in ("main", "keep_me", "drop_me"):
        db.upsert_library_decl(conn, problem="p", slug=s, source_goal_id=None)
    db.set_library_verdict(conn, problem="p", slug="keep_me", verdict="keep")
    db.set_library_verdict(conn, problem="p", slug="drop_me", verdict="drop",
                           citation="x")
    ad = tmp_path / "att"; ad.mkdir()
    ctx = lib.compile_librarian_context(
        conn, problem="p", work_kind="classify", attempts_dir=ad,
        workspace=tmp_path)
    text = ctx.read_text(encoding="utf-8")
    assert "keep_me" in text
    assert "drop_me" not in text  # dropped decls not in layout surface


def test_context_migrate_lists_decls(conn, tmp_path):
    # Per-file: the migrate context lists each decl with its statement
    # (signature to copy) + a pointer to the proof source, not the whole
    # embedded file.
    g = db.insert_goal(conn, problem="p", slug="lemma_a",
                       lean_path="Problems/p/proofs/L_lemma_a.lean",
                       statement="lemma_a : True", origin="backward",
                       kind="theorem")
    conn.execute("UPDATE goals SET status='proved' WHERE id=?", (g,))
    conn.commit()
    db.upsert_library_decl(conn, problem="p", slug="lemma_a",
                           source_goal_id=g)
    db.set_library_verdict(conn, problem="p", slug="lemma_a", verdict="keep")
    db.set_library_classification(conn, problem="p", slug="lemma_a",
                                  target_file="Library/A/Foo.lean",
                                  target_name=None, file_order=0)
    ad = tmp_path / "att"; ad.mkdir()
    ctx = lib.compile_librarian_context(
        conn, problem="p", work_kind="migrate", attempts_dir=ad,
        workspace=tmp_path, target_file="Library/A/Foo.lean")
    text = ctx.read_text(encoding="utf-8")
    assert "Library/A/Foo.lean" in text          # target file
    assert "Library.A.Foo" in text               # module name
    assert "lemma_a" in text                      # decl listed
    assert "lemma_a : True" in text               # statement (signature)
    assert "L_lemma_a.lean" in text               # proof source pointer
    assert "copy verbatim" in text


def test_context_migrate_defs_decl_embeds_defs_source(conn, tmp_path):
    # A Defs.lean declaration has no goal row; the migrate context embeds
    # the problem's Defs.lean so the agent reproduces the locked body.
    pdir = tmp_path / "Problems" / "p"
    pdir.mkdir(parents=True)
    (pdir / "Defs.lean").write_text(
        "import Mathlib\nnamespace Problems.p\n"
        "def IsFoo : Prop := True\nend Problems.p\n", encoding="utf-8")
    db.upsert_library_decl(conn, problem="p", slug="IsFoo",
                           source_goal_id=None)
    db.set_library_verdict(conn, problem="p", slug="IsFoo", verdict="keep")
    db.set_library_classification(conn, problem="p", slug="IsFoo",
                                  target_file="Library/P/Defs.lean",
                                  target_name=None, file_order=0)
    ad = tmp_path / "att"; ad.mkdir()
    ctx = lib.compile_librarian_context(
        conn, problem="p", work_kind="migrate", attempts_dir=ad,
        workspace=tmp_path, target_file="Library/P/Defs.lean")
    text = ctx.read_text(encoding="utf-8")
    assert "def IsFoo : Prop := True" in text   # Defs.lean source embedded
    assert "Library/P/Defs.lean" in text


def test_context_migrate_requires_target(conn, tmp_path):
    ad = tmp_path / "att"; ad.mkdir()
    with pytest.raises(ValueError):
        lib.compile_librarian_context(
            conn, problem="p", work_kind="migrate", attempts_dir=ad,
            workspace=tmp_path)


def test_context_unknown_work_kind(conn, tmp_path):
    ad = tmp_path / "att"; ad.mkdir()
    with pytest.raises(ValueError):
        lib.compile_librarian_context(
            conn, problem="p", work_kind="bogus", attempts_dir=ad,
            workspace=tmp_path)


# ---------------------------------------------------------------------
# Stage D — run_librarian dispatch (spawn mocked; no gateway)
# ---------------------------------------------------------------------

def _seed_proved(conn, slug, stmt, *, origin="backward"):
    g = db.insert_goal(conn, problem="p", slug=slug,
                       lean_path=f"proofs/L_{slug}.lean",
                       statement=stmt, origin=origin, kind="theorem")
    conn.execute("UPDATE goals SET status='proved' WHERE id=?", (g,))
    conn.commit()
    return g


def test_run_librarian_bad_work_kind(conn, tmp_path):
    r = lib.run_librarian(conn, problem="p", work_kind="bogus",
                          workspace=tmp_path, pipeline_id="pid")
    assert r.outcome == "failed"
    assert r.failure_reason == "librarian_bad_work_kind"


def _no_spawn(**kw):
    raise AssertionError("mechanical step must not spawn an agent")


def test_run_keepall_keeps_reachable_closure(conn, tmp_path, monkeypatch):
    # v0.3: `dedup` is the mechanical keep step (`_run_keepall`) — NO spawn,
    # keeps main's LIVE dependency closure; orphan proved goals (unreachable
    # from main) are skipped as debris.
    _seed_proved(conn, "main", "M", origin="root")
    _seed_proved(conn, "lemma_a", "A")
    _seed_proved(conn, "orphan", "O")    # proved but unreachable from main

    import Tooling.agent as agent
    monkeypatch.setattr(agent, "spawn_llm", _no_spawn)   # keep is spawn-free
    # main reaches lemma_a; `orphan` is proving debris.
    monkeypatch.setattr(lib, "_reachable_from_root",
                        lambda *a, **k: {"main", "lemma_a"})

    r = lib.run_librarian(conn, problem="p", work_kind="dedup",
                          workspace=tmp_path, pipeline_id="pid")
    assert r.outcome == "success", r.failure_detail
    deduped = {x["slug"] for x in db.library_decls_for(conn, "p",
                                                       lifecycle="deduped")}
    assert deduped == {"main", "lemma_a"}        # orphan excluded
    all_slugs = {x["slug"] for x in db.library_decls_for(conn, "p")}
    assert "orphan" not in all_slugs             # debris not inventoried
    assert db.library_decls_for(conn, "p", lifecycle="dropped") == []


def test_run_classify_end_to_end(conn, tmp_path, monkeypatch):
    _seed_proved(conn, "main", "M", origin="root")
    _seed_proved(conn, "lemma_a", "A")
    for s in ("main", "lemma_a"):
        db.upsert_library_decl(conn, problem="p", slug=s, source_goal_id=None)
        db.set_library_verdict(conn, problem="p", slug=s, verdict="keep")

    import Tooling.agent as agent
    ad = agent.attempts_dir_for(tmp_path, "pid")
    ad.mkdir(parents=True, exist_ok=True)

    def fake_spawn(**kw):
        (ad / "plan.json").write_text(json.dumps({"files": [
            {"path": "Library/A/Main.lean", "imports": [],
             "decls": ["main", "lemma_a"]},
        ]}), encoding="utf-8")
        return 0
    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)

    r = lib.run_librarian(conn, problem="p", work_kind="classify",
                          workspace=tmp_path, pipeline_id="pid")
    assert r.outcome == "success", r.failure_detail
    classified = db.library_decls_for(conn, "p", lifecycle="classified")
    assert {x["slug"] for x in classified} == {"main", "lemma_a"}


def test_run_no_output_fails(conn, tmp_path, monkeypatch):
    # A structured agentic step (classify) whose agent emits no plan.json fails.
    # (v0.3: dedup is mechanical, so classify is the structured step to check.)
    _seed_proved(conn, "main", "M", origin="root")
    db.upsert_library_decl(conn, problem="p", slug="main", source_goal_id=None)
    db.set_library_verdict(conn, problem="p", slug="main", verdict="keep")
    import Tooling.agent as agent
    ad = agent.attempts_dir_for(tmp_path, "pid")
    ad.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(agent, "spawn_llm", lambda **kw: 0)
    r = lib.run_librarian(conn, problem="p", work_kind="classify",
                          workspace=tmp_path, pipeline_id="pid")
    assert r.outcome == "failed" and r.failure_reason == "agent_no_output"


def test_verify_classify_rejects_owned_file():
    # migrate writes whole files — a plan placing decls into a file another
    # problem already owns can only clobber (form_coord 2026-06-11).
    plan = _plan([{"path": "Library/A/Taken.lean", "imports": [],
                   "decls": ["a"]}])
    err = lib.verify_classify(plan, {"a"},
                              owned_files={"Library/A/Taken.lean"})
    assert "another problem" in err and "Taken.lean" in err
    assert lib.verify_classify(plan, {"a"}, owned_files=set()) == ""
    assert lib.verify_classify(plan, {"a"}) == ""             # back-compat
