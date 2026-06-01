"""Librarian pipeline stage A — pure parse + verify + commit for the
dedup and classify work kinds (no gateway / no LLM)."""
from __future__ import annotations

import json

import pytest

from Tooling.state import db
from Tooling.pipeline import librarian as lib


# ---------------------------------------------------------------------
# parse_dedup
# ---------------------------------------------------------------------

def test_parse_dedup_array():
    js = json.dumps([
        {"slug": "a", "verdict": "keep", "reason": "novel"},
        {"slug": "b", "verdict": "cite-mathlib", "mathlib_name": "map_sum"},
    ])
    out, err = lib.parse_dedup(js)
    assert err == ""
    assert [v.slug for v in out] == ["a", "b"]
    assert out[1].citation == "map_sum"


def test_parse_dedup_single_object():
    out, err = lib.parse_dedup('{"slug":"a","verdict":"keep"}')
    assert err == "" and len(out) == 1


def test_parse_dedup_strips_fences():
    js = "```json\n[{\"slug\":\"a\",\"verdict\":\"drop\",\"mathlib_name\":\"x\"}]\n```"
    out, err = lib.parse_dedup(js)
    assert err == "" and out[0].verdict == "drop"


def test_parse_dedup_bad_verdict():
    out, err = lib.parse_dedup('[{"slug":"a","verdict":"frobnicate"}]')
    assert out is None and "not in" in err


def test_parse_dedup_missing_slug():
    out, err = lib.parse_dedup('[{"verdict":"keep"}]')
    assert out is None and "slug" in err


def test_parse_dedup_invalid_json():
    out, err = lib.parse_dedup("not json {")
    assert out is None and "invalid JSON" in err


def test_parse_dedup_empty():
    out, err = lib.parse_dedup("[]")
    assert out is None and "empty" in err


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
# verify_dedup
# ---------------------------------------------------------------------

def test_verify_dedup_ok():
    vs = [lib.DedupVerdict("a", "keep"),
          lib.DedupVerdict("b", "cite-mathlib", "map_sum")]
    assert lib.verify_dedup(vs, {"a", "b"}) == ""


def test_verify_dedup_unknown_slug():
    vs = [lib.DedupVerdict("ghost", "keep")]
    assert "inventory" in lib.verify_dedup(vs, {"a"})


def test_verify_dedup_named_verdict_without_citation():
    vs = [lib.DedupVerdict("a", "cite-mathlib", None)]
    assert "named target" in lib.verify_dedup(vs, {"a"})


def test_verify_dedup_merge_to_nonsibling():
    vs = [lib.DedupVerdict("a", "merge", "outsider")]
    assert "sibling" in lib.verify_dedup(vs, {"a", "b"})


def test_verify_dedup_merge_to_sibling_ok():
    vs = [lib.DedupVerdict("a", "merge", "b")]
    assert lib.verify_dedup(vs, {"a", "b"}) == ""


def test_verify_dedup_duplicate():
    vs = [lib.DedupVerdict("a", "keep"), lib.DedupVerdict("a", "drop", "x")]
    assert "duplicate" in lib.verify_dedup(vs, {"a"})


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


def test_commit_dedup_then_classify(conn, tmp_path):
    for s in ("a", "b", "c"):
        db.upsert_library_decl(conn, problem="p", slug=s, source_goal_id=None)
    lib.commit_dedup(conn, "p", [
        lib.DedupVerdict("a", "keep"),
        lib.DedupVerdict("b", "keep"),
        lib.DedupVerdict("c", "drop", "mathlib_thing"),
    ])
    deduped = {r["slug"] for r in db.library_decls_for(conn, "p",
                                                       lifecycle="deduped")}
    assert deduped == {"a", "b"}
    assert {r["slug"] for r in db.library_decls_for(conn, "p",
                                                    lifecycle="dropped")} == {"c"}

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
# Stage B — migrate_commit_gate (injectable build_verifier, no gateway)
# ---------------------------------------------------------------------

from pathlib import Path as _P


def _ok_build(_text):
    return (True, "")


def _fail_build(msg):
    def _v(_text):
        return (False, msg)
    return _v


def test_migrate_gate_clean_passes():
    patch = ("import Mathlib\nimport Library.A.Foo\n"
             "namespace Library.A\n"
             "theorem t : True := trivial\nend Library.A\n")
    r = lib.migrate_commit_gate(patch, _P("Library/A/Bar.lean"),
                                build_verifier=_ok_build)
    assert r.ok, r.detail


def test_migrate_gate_rejects_problems_import():
    patch = ("import Mathlib\nimport Problems.p.Defs\n"
             "theorem t : True := trivial\n")
    r = lib.migrate_commit_gate(patch, _P("Library/A/Bar.lean"),
                                build_verifier=_ok_build)
    assert not r.ok and "Problems.p.Defs" in r.detail


def test_migrate_gate_rejects_sorry():
    patch = ("import Mathlib\n"
             "theorem t : True := by sorry\n")
    r = lib.migrate_commit_gate(patch, _P("Library/A/Bar.lean"),
                                build_verifier=_ok_build)
    assert not r.ok and "sorry" in r.detail


def test_migrate_gate_rejects_build_failure():
    patch = ("import Mathlib\n"
             "theorem t : True := trivial\n")
    r = lib.migrate_commit_gate(
        patch, _P("Library/A/Bar.lean"),
        build_verifier=_fail_build("unknown identifier 'foo'"))
    assert not r.ok and "build failed" in r.detail
    assert "foo" in r.detail


def test_migrate_gate_closure_checked_before_build():
    """A Problems import is caught even if the build would pass — the
    cheap text gate runs first."""
    patch = "import Problems.x.Defs\ntheorem t : True := trivial\n"
    called = {"n": 0}
    def _spy(_t):
        called["n"] += 1
        return (True, "")
    r = lib.migrate_commit_gate(patch, _P("Library/A/Bar.lean"),
                                build_verifier=_spy)
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


def _ok_axiom(_text, _fq, _wl):
    return (True, "")


def _rogue_axiom(_text, _fq, _wl):
    return (False, "rogue axioms: ['sorryAx']")


def test_migrate_gate_axiom_clean_passes():
    patch = ("import Mathlib\nnamespace Library.A\n"
             "theorem t : True := trivial\nend Library.A\n")
    r = lib.migrate_commit_gate(
        patch, _P("Library/A/Bar.lean"), whitelist=["propext"],
        build_verifier=_ok_build, axiom_verifier=_ok_axiom)
    assert r.ok, r.detail


def test_migrate_gate_rejects_rogue_axiom():
    """build passes but the decl's transitive axiom set escapes the
    whitelist (e.g. sorryAx from an imported stub) → reject."""
    patch = ("import Mathlib\nnamespace Library.A\n"
             "theorem t : True := trivial\nend Library.A\n")
    r = lib.migrate_commit_gate(
        patch, _P("Library/A/Bar.lean"), whitelist=["propext"],
        build_verifier=_ok_build, axiom_verifier=_rogue_axiom)
    assert not r.ok
    assert "axiom check failed" in r.detail and "sorryAx" in r.detail


def test_migrate_gate_axiom_skipped_without_whitelist():
    """whitelist=None (the unit-test default) skips the axiom check — the
    axiom_verifier must not even be called."""
    patch = ("import Mathlib\nnamespace Library.A\n"
             "theorem t : True := trivial\nend Library.A\n")
    called = {"n": 0}
    def _spy(_t, _fq, _wl):
        called["n"] += 1
        return (True, "")
    r = lib.migrate_commit_gate(
        patch, _P("Library/A/Bar.lean"),
        build_verifier=_ok_build, axiom_verifier=_spy)
    assert r.ok and called["n"] == 0


def test_migrate_gate_axiom_unextractable_name_rejected():
    """whitelist set but the patch has no named decl → the gate fails
    rather than silently skipping the axiom check (keeps the per-file
    invariant honest)."""
    patch = "import Mathlib\ninstance : Inhabited Nat := ⟨0⟩\n"
    r = lib.migrate_commit_gate(
        patch, _P("Library/A/Bar.lean"), whitelist=["propext"],
        build_verifier=_ok_build, axiom_verifier=_ok_axiom)
    assert not r.ok
    assert "no named declaration found" in r.detail


# ---------------------------------------------------------------------
# Stage C — compile_librarian_context
# ---------------------------------------------------------------------

def _goal_with_stmt(conn, slug, stmt):
    return db.insert_goal(conn, problem="p", slug=slug,
                          lean_path=f"proofs/L_{slug}.lean",
                          statement=stmt, origin="backward", kind="theorem")


def test_context_dedup_lists_statements(conn, tmp_path):
    root = db.insert_goal(conn, problem="p", slug="main",
                          lean_path="Problems/p/Root.lean",
                          statement="MainStmt", origin="root", kind="theorem")
    conn.execute("UPDATE goals SET status='proved' WHERE id=?", (root,))
    g = _goal_with_stmt(conn, "lemma_a", "LemmaAStmt")
    conn.execute("UPDATE goals SET status='proved' WHERE id=?", (g,))
    conn.commit()
    ad = tmp_path / "att"; ad.mkdir()
    ctx = lib.compile_librarian_context(
        conn, problem="p", work_kind="dedup", attempts_dir=ad,
        workspace=tmp_path)
    text = ctx.read_text(encoding="utf-8")
    assert "lemma_a" in text and "LemmaAStmt" in text
    assert "main" in text and "MainStmt" in text


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


def test_run_dedup_end_to_end(conn, tmp_path, monkeypatch):
    _seed_proved(conn, "main", "M", origin="root")
    _seed_proved(conn, "lemma_a", "A")
    _seed_proved(conn, "lemma_b", "B")

    import Tooling.agent as agent
    ad = agent.attempts_dir_for(tmp_path, "pid")
    ad.mkdir(parents=True, exist_ok=True)

    def fake_spawn(**kw):
        (ad / "plan.json").write_text(json.dumps([
            {"slug": "main", "verdict": "keep"},
            {"slug": "lemma_a", "verdict": "keep"},
            {"slug": "lemma_b", "verdict": "drop", "mathlib_name": "map_sum"},
        ]), encoding="utf-8")
        return 0
    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)

    r = lib.run_librarian(conn, problem="p", work_kind="dedup",
                          workspace=tmp_path, pipeline_id="pid")
    assert r.outcome == "success", r.failure_detail
    deduped = {x["slug"] for x in db.library_decls_for(conn, "p",
                                                       lifecycle="deduped")}
    assert deduped == {"main", "lemma_a"}
    dropped = {x["slug"] for x in db.library_decls_for(conn, "p",
                                                       lifecycle="dropped")}
    assert dropped == {"lemma_b"}


def test_run_dedup_rejects_bad_schema(conn, tmp_path, monkeypatch):
    _seed_proved(conn, "main", "M", origin="root")
    import Tooling.agent as agent
    ad = agent.attempts_dir_for(tmp_path, "pid")
    ad.mkdir(parents=True, exist_ok=True)

    def fake_spawn(**kw):
        (ad / "plan.json").write_text('[{"slug":"main","verdict":"xyz"}]',
                                      encoding="utf-8")
        return 0
    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)
    r = lib.run_librarian(conn, problem="p", work_kind="dedup",
                          workspace=tmp_path, pipeline_id="pid")
    assert r.outcome == "failed"
    assert r.failure_reason == "librarian_schema_invalid"


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
    _seed_proved(conn, "main", "M", origin="root")
    import Tooling.agent as agent
    ad = agent.attempts_dir_for(tmp_path, "pid")
    ad.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(agent, "spawn_llm", lambda **kw: 0)
    r = lib.run_librarian(conn, problem="p", work_kind="dedup",
                          workspace=tmp_path, pipeline_id="pid")
    assert r.outcome == "failed" and r.failure_reason == "agent_no_output"
