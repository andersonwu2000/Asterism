"""Mechanical migrate pre-pass wiring (librarian._mechanical_migrate_file
+ _commit_migrated_file). Offline — verifiers injected, no gateway/LLM.

Verifies the Phase-1 path assembles a classified file by pure relabel and
commits it through the shared gate without ever spawning an agent.
"""
from __future__ import annotations

import pytest

from Tooling.state import db
from Tooling.pipeline import librarian as lib
from Tooling.pipeline import PipelineResult

PNS = "Problems.p"  # problem name "p" → namespace Problems.p


@pytest.fixture
def conn():
    c = db.connect(":memory:")
    db.init_schema(c)
    c.execute("INSERT INTO problems (name, manifest_path, created_at, "
              "bootstrap_done) VALUES ('p','',?,1)", (db.now(),))
    c.commit()
    return c


def _seed_classified(conn, slug, stmt, target_file, order):
    g = db.insert_goal(conn, problem="p", slug=slug,
                       lean_path=f"Problems/p/proofs/L_{slug}.lean",
                       statement=stmt, origin="backward", kind="theorem")
    conn.execute("UPDATE goals SET status='proved' WHERE id=?", (g,))
    conn.commit()
    db.upsert_library_decl(conn, problem="p", slug=slug, source_goal_id=g)
    db.set_library_verdict(conn, problem="p", slug=slug, verdict="keep")
    db.set_library_classification(conn, problem="p", slug=slug,
                                  target_file=target_file, target_name=None,
                                  file_order=order)


def _write_proof(workspace, slug, body):
    pdir = workspace / "Problems" / "p" / "proofs"
    pdir.mkdir(parents=True, exist_ok=True)
    (pdir / f"L_{slug}.lean").write_text(body, encoding="utf-8")


def test_mechanical_assembles_self_contained_file(conn, tmp_path):
    tf = "Library/P/Foo.lean"
    _seed_classified(conn, "lem_a", "True", tf, 0)
    _write_proof(tmp_path, "lem_a",
                 "import Mathlib\n"
                 f"import {PNS}.Defs\n"
                 f"namespace {PNS}\n"
                 "theorem lem_a : True := by trivial\n"
                 f"end {PNS}\n")
    rows = [r for r in db.library_decls_for(conn, "p")
            if r["target_file"] == tf and r["lifecycle"] == "classified"]
    text, holes, _asm = lib._mechanical_migrate_file(
        conn, problem="p", workspace=tmp_path, target_file=tf,
        target_module="Library.P.Foo", rows=rows)
    assert text is not None
    assert holes == []
    assert "namespace Library.P.Foo" in text
    assert "theorem lem_a : True := by trivial" in text
    assert "Problems." not in text


def test_mechanical_header_carries_filedep_imports(conn, tmp_path,
                                                   monkeypatch):
    # A decl can cite a cross-file sibling transitively (no explicit
    # `import …proofs.L_<sub>` in its own source), so relabel never emits the
    # sibling import. The authoritative file_dependency_graph still records the
    # edge (it drives migrate order), so the assembled header must carry it —
    # else the full-qualified reference lands in a header with no import for
    # that module and build-fails with Unknown identifier. Regression for the
    # BlockBasis → NilpotentFamily e2e failure (mech.header is the single
    # source consumed by the 0-hole commit, incremental `_stage`, and the
    # final assembled file).
    tf = "Library/P/Foo.lean"
    dep = "Library/P/Dep.lean"
    _seed_classified(conn, "lem_a", "True", tf, 0)
    _write_proof(tmp_path, "lem_a",
                 "import Mathlib\n"
                 f"namespace {PNS}\n"
                 "theorem lem_a : True := by trivial\n"
                 f"end {PNS}\n")
    monkeypatch.setattr(lib, "file_dependency_graph",
                        lambda *a, **k: {tf: {dep}})
    rows = [r for r in db.library_decls_for(conn, "p")
            if r["target_file"] == tf and r["lifecycle"] == "classified"]
    text, holes, asm = lib._mechanical_migrate_file(
        conn, problem="p", workspace=tmp_path, target_file=tf,
        target_module="Library.P.Foo", rows=rows)
    assert "import Library.P.Dep" in asm.header
    assert "import Library.P.Dep" in text


def test_ready_file_work_dag_scheduling(conn, tmp_path, monkeypatch):
    # #92 scheduler primitive: independent files are ready together; a file
    # depending on another waits until that dep is migrated (v0.3: done =
    # migrated, no cleanup); in_flight files are excluded.
    def _seed(slug, tf, lifecycle):
        g = db.insert_goal(conn, problem="p", slug=slug,
                           lean_path=f"Problems/p/proofs/L_{slug}.lean",
                           statement="True", origin="backward", kind="theorem")
        conn.execute("UPDATE goals SET status='proved' WHERE id=?", (g,))
        db.upsert_library_decl(conn, problem="p", slug=slug, source_goal_id=g)
        db.set_library_verdict(conn, problem="p", slug=slug, verdict="keep")
        db.set_library_classification(conn, problem="p", slug=slug,
                                      target_file=tf, target_name=None,
                                      file_order=0)
        conn.execute("UPDATE library_decls SET lifecycle=? WHERE problem='p' "
                     "AND slug=?", (lifecycle, slug))
        conn.commit()
    # B depends on A; C is independent.
    monkeypatch.setattr(lib, "file_dependency_graph",
                        lambda *a, **k: {"B.lean": {"A.lean"}, "A.lean": set(),
                                         "C.lean": set()})

    # (1) all classified: A and C migrate-ready; B blocked (A not done).
    _seed("a", "A.lean", "classified")
    _seed("b", "B.lean", "classified")
    _seed("c", "C.lean", "classified")
    work = lib.ready_file_work(conn, problem="p", workspace=tmp_path)
    assert work == [("migrate", "A.lean"), ("migrate", "C.lean")]

    # (2) in_flight excludes A.
    work = lib.ready_file_work(conn, problem="p", workspace=tmp_path,
                               in_flight={"A.lean"})
    assert work == [("migrate", "C.lean")]

    # (3) A and C migrated: B becomes migrate-ready (dep A importable); A and C
    #     are done (v0.3: migrated = done, no per-file cleanup work).
    conn.execute("UPDATE library_decls SET lifecycle='migrated' WHERE problem='p'"
                 " AND slug IN ('a','c')")
    conn.commit()
    work = lib.ready_file_work(conn, problem="p", workspace=tmp_path)
    assert work == [("migrate", "B.lean")]    # only B left; A and C done


def test_mechanical_missing_proof_file_is_integrity_error(conn, tmp_path):
    # A goal-backed classified decl whose proof file is missing on disk is
    # file↔DB drift — raised loud (not masked by a cold from-scratch spawn).
    _seed_classified(conn, "ghost", "True", "Library/P/Bar.lean", 0)
    rows = [r for r in db.library_decls_for(conn, "p")
            if r["lifecycle"] == "classified"]
    with pytest.raises(lib._MechIntegrityError):
        lib._mechanical_migrate_file(
            conn, problem="p", workspace=tmp_path,
            target_file="Library/P/Bar.lean",
            target_module="Library.P.Bar", rows=rows)


def test_commit_migrated_file_marks_all(conn, tmp_path):
    # End-to-end of the shared commit with injected (passing) verifiers:
    # assemble mechanically, then commit → both decls become 'migrated'.
    tf = "Library/P/Foo.lean"
    _seed_classified(conn, "lem_a", "True", tf, 0)
    _seed_classified(conn, "lem_b", "True", tf, 1)
    for slug in ("lem_a", "lem_b"):
        _write_proof(tmp_path, slug,
                     "import Mathlib\n"
                     f"namespace {PNS}\n"
                     f"theorem {slug} : True := by trivial\n"
                     f"end {PNS}\n")
    rows = [r for r in db.library_decls_for(conn, "p")
            if r["target_file"] == tf and r["lifecycle"] == "classified"]
    rows.sort(key=lambda r: r["file_order"])
    text, holes, _asm = lib._mechanical_migrate_file(
        conn, problem="p", workspace=tmp_path, target_file=tf,
        target_module="Library.P.Foo", rows=rows)
    assert text is not None
    assert holes == []

    res = lib._commit_migrated_file(
        text, conn=conn, problem="p", workspace=tmp_path,
        target_path=tmp_path / tf, target_module="Library.P.Foo",
        ordered_slugs=["lem_a", "lem_b"], defs_names=[],
        whitelist=None,
        probe_verifier=lambda _t: (True, "", {}),
        olean_writer=lambda _p: (True, ""))
    assert res.outcome == "success", res.failure_detail
    migrated = {r["slug"] for r in db.library_decls_for(conn, "p",
                                                        lifecycle="migrated")}
    assert migrated == {"lem_a", "lem_b"}
    # File written to disk.
    assert (tmp_path / tf).exists()
    # target_name backfilled to the Library FQ name.
    by = {r["slug"]: r for r in db.library_decls_for(conn, "p")}
    assert by["lem_a"]["target_name"] == "Library.P.Foo.lem_a"


def test_commit_rolls_back_on_gate_fail(conn, tmp_path):
    tf = "Library/P/Foo.lean"
    _seed_classified(conn, "lem_a", "True", tf, 0)
    _write_proof(tmp_path, "lem_a",
                 "import Mathlib\n"
                 f"namespace {PNS}\n"
                 "theorem lem_a : True := by trivial\n"
                 f"end {PNS}\n")
    rows = [r for r in db.library_decls_for(conn, "p")
            if r["target_file"] == tf and r["lifecycle"] == "classified"]
    text, _holes, _asm = lib._mechanical_migrate_file(
        conn, problem="p", workspace=tmp_path, target_file=tf,
        target_module="Library.P.Foo", rows=rows)
    res = lib._commit_migrated_file(
        text, conn=conn, problem="p", workspace=tmp_path,
        target_path=tmp_path / tf, target_module="Library.P.Foo",
        ordered_slugs=["lem_a"], defs_names=[], whitelist=None,
        probe_verifier=lambda _t: (False, "boom", {}))
    assert res.outcome == "failed"
    # not advanced to migrated; file rolled back (build gate fails pre-write)
    assert db.library_decls_for(conn, "p", lifecycle="migrated") == []


# --- root cause 1: verbatim-merge citation must compare full signature ---

def test_decl_signature_strips_name_and_body():
    # Two decls with the SAME binders + conclusion but different names →
    # identical signatures (name stripped, body stripped).
    a = ("namespace N\ntheorem foo (n : Nat) : n = n := by rfl\nend N\n")
    b = ("namespace N\ntheorem bar (n : Nat) : n = n := by simp\nend N\n")
    assert lib._decl_signature(a) == lib._decl_signature(b)
    assert lib._decl_signature(a) == "(n : Nat) : n = n"


def test_decl_signature_differs_on_extra_binder():
    # Same conclusion (`n = n`), but one takes an extra hypothesis → the
    # signatures must differ (the root-cause-1 case: `goals.statement`
    # conclusion-only equality would wrongly call these mergeable).
    base = "namespace N\ntheorem foo (n : Nat) : n = n := by rfl\nend N\n"
    extra = ("namespace N\n"
             "theorem foo_of_h (n : Nat) (h : n = 0) : n = n := by rfl\nend N\n")
    assert lib._decl_signature(base) != lib._decl_signature(extra)


def test_merge_different_binders_declines_citation(conn, tmp_path):
    # `foo` (keep) calls a merged sibling `bar_of_h` whose canonical `bar`
    # has the SAME conclusion but FEWER binders. The mechanical citation
    # rewrite would mis-position args, so it must NOT enter citation_map →
    # `bar_of_h` stays referenced → relabel declines `foo` → whole file None.
    tf = "Library/P/Foo.lean"
    _seed_classified(conn, "foo", "True", tf, 1)
    # bar is the canonical keep sibling (1 binder); bar_of_h merges into it
    # but takes an extra hypothesis (2 binders), same conclusion.
    g_bar = db.insert_goal(conn, problem="p", slug="bar",
                           lean_path="Problems/p/proofs/L_bar.lean",
                           statement="n = n", origin="backward", kind="theorem")
    conn.execute("UPDATE goals SET status='proved' WHERE id=?", (g_bar,))
    db.upsert_library_decl(conn, problem="p", slug="bar", source_goal_id=g_bar)
    db.set_library_verdict(conn, problem="p", slug="bar", verdict="keep")
    db.set_library_classification(conn, problem="p", slug="bar",
                                  target_file=tf, target_name=None, file_order=0)
    g_h = db.insert_goal(conn, problem="p", slug="bar_of_h",
                         lean_path="Problems/p/proofs/L_bar_of_h.lean",
                         statement="n = n", origin="backward", kind="theorem")
    conn.execute("UPDATE goals SET status='proved' WHERE id=?", (g_h,))
    db.upsert_library_decl(conn, problem="p", slug="bar_of_h", source_goal_id=g_h)
    db.set_library_verdict(conn, problem="p", slug="bar_of_h",
                           verdict="merge", citation="bar")
    conn.commit()
    _write_proof(tmp_path, "bar",
                 "import Mathlib\nnamespace " + PNS +
                 "\ntheorem bar (n : Nat) : n = n := by rfl\nend " + PNS + "\n")
    _write_proof(tmp_path, "bar_of_h",
                 "import Mathlib\nnamespace " + PNS +
                 "\ntheorem bar_of_h (n : Nat) (h : n = 0) : n = n := by rfl\n"
                 "end " + PNS + "\n")
    _write_proof(tmp_path, "foo",
                 "import Mathlib\nimport " + PNS + ".proofs.L_bar_of_h\n"
                 "namespace " + PNS + "\n"
                 "theorem foo (n : Nat) : True := by\n"
                 "  have := bar_of_h n rfl\n  trivial\nend " + PNS + "\n")
    rows = [r for r in db.library_decls_for(conn, "p")
            if r["target_file"] == tf and r["lifecycle"] == "classified"]
    rows.sort(key=lambda r: r["file_order"])
    text, holes, _asm = lib._mechanical_migrate_file(
        conn, problem="p", workspace=tmp_path, target_file=tf,
        target_module="Library.P.Foo", rows=rows)
    # bar_of_h NOT redirected (binder mismatch) → foo can't be completed
    # mechanically, but its signature is clean → seeded as a sorry hole
    # (NOT silently mis-renamed to `bar`, which would build-fail).
    assert text is not None
    assert holes == ["foo"]
    assert "theorem foo (n : Nat) : True :=" in text
    assert "sorry" in text
    assert "bar_of_h" not in text          # body (with the bad ref) dropped


# --- G3: migrate Context surfaces sibling redirects ---

def test_migrate_context_shows_sibling_redirects(conn, tmp_path):
    # `foo` (keep) cites a dropped sibling `bar` whose dedup citation is a
    # mathlib lemma → migrate Context must list the redirect so the seed LLM
    # knows what to replace `bar` with when filling foo's body.
    tf = "Library/P/Foo.lean"
    _seed_classified(conn, "foo", "True", tf, 0)
    g = db.insert_goal(conn, problem="p", slug="bar",
                       lean_path="Problems/p/proofs/L_bar.lean", statement="True",
                       origin="backward", kind="theorem")
    conn.execute("UPDATE goals SET status='proved' WHERE id=?", (g,))
    db.upsert_library_decl(conn, problem="p", slug="bar", source_goal_id=g)
    db.set_library_verdict(conn, problem="p", slug="bar", verdict="drop",
                           citation="Mathlib.foo_thm")
    conn.commit()
    _write_proof(tmp_path, "foo",
                 "import Mathlib\nimport " + PNS + ".proofs.L_bar\n"
                 "namespace " + PNS + "\n"
                 "theorem foo : True := by have := bar; trivial\n"
                 "end " + PNS + "\n")
    attempts = tmp_path / ".attempts"
    attempts.mkdir()
    ctx = lib.compile_librarian_context(
        conn, problem="p", work_kind="migrate", attempts_dir=attempts,
        workspace=tmp_path, target_file=tf)
    body = ctx.read_text(encoding="utf-8")
    assert "Sibling redirects" in body
    assert "`bar` → `Mathlib.foo_thm`" in body


def test_migrate_context_surfaces_absorbed_sibling_and_strategy(conn, tmp_path):
    # A hole `foo` whose proof alias points to a strategy that uses a sibling
    # `helper` dedup'd INTO it (merge, no Library home). Context must (②) resolve
    # the alias to the real `_strategy_s*.lean`, and (①) list the absorbed
    # sibling + its proof so the agent inlines it instead of hunting.
    tf = "Library/P/Foo.lean"
    _seed_classified(conn, "foo", "True", tf, 0)          # the hole
    g = db.insert_goal(conn, problem="p", slug="helper",
                       lean_path="Problems/p/proofs/L_helper.lean",
                       statement="True", origin="backward", kind="theorem")
    conn.execute("UPDATE goals SET status='proved' WHERE id=?", (g,))
    db.upsert_library_decl(conn, problem="p", slug="helper", source_goal_id=g)
    db.set_library_verdict(conn, problem="p", slug="helper", verdict="merge",
                           citation="foo")          # merged INTO foo, no home
    conn.commit()
    # foo's proof: alias → strategy s700, which imports (uses) L_helper.
    _write_proof(tmp_path, "foo",
                 "import Mathlib\nimport " + PNS + ".proofs._strategy_s700\n"
                 "namespace " + PNS + "\ndef foo := @" + PNS + ".s700\n"
                 "end " + PNS + "\n")
    proofs = tmp_path / "Problems" / "p" / "proofs"
    (proofs / "_strategy_s700.lean").write_text(
        "import Mathlib\nimport " + PNS + ".proofs.L_helper\n"
        "namespace " + PNS + "\n"
        "theorem s700 : True := by have := helper; trivial\nend " + PNS + "\n",
        encoding="utf-8")
    _write_proof(tmp_path, "helper",
                 "import Mathlib\nnamespace " + PNS +
                 "\ntheorem helper : True := by trivial\nend " + PNS + "\n")
    attempts = tmp_path / ".attempts"
    attempts.mkdir()
    ctx = lib.compile_librarian_context(
        conn, problem="p", work_kind="migrate", attempts_dir=attempts,
        workspace=tmp_path, target_file=tf, holes=["foo"], solo_hole="foo")
    body = ctx.read_text(encoding="utf-8")
    # ② alias resolved to the real strategy proof body
    assert "actual proof body" in body
    assert "_strategy_s700.lean" in body
    # ① absorbed sibling surfaced with its proof source
    assert "absorbed siblings" in body
    assert "`helper` (merge)" in body
    assert "L_helper.lean" in body


# --- seed mode: best-effort assembly with sorry holes ---

def test_seed_mode_clean_decl_plus_hole(conn, tmp_path):
    # `clean` relabels fully; `holey` cites a non-keep sibling in its body →
    # seeded as a sorry hole. Result: full text + holes == ["holey"], all
    # decls present and in order (positional pairing preserved).
    tf = "Library/P/Foo.lean"
    _seed_classified(conn, "clean", "True", tf, 0)
    _seed_classified(conn, "holey", "True", tf, 1)
    # a dropped (non-keep) sibling `gone` that holey's body references
    g = db.insert_goal(conn, problem="p", slug="gone",
                       lean_path="Problems/p/proofs/L_gone.lean", statement="True",
                       origin="backward", kind="theorem")
    conn.execute("UPDATE goals SET status='proved' WHERE id=?", (g,))
    db.upsert_library_decl(conn, problem="p", slug="gone", source_goal_id=g)
    db.set_library_verdict(conn, problem="p", slug="gone", verdict="drop",
                           citation="Trivial.thing")
    conn.commit()
    _write_proof(tmp_path, "clean",
                 "import Mathlib\n" + f"namespace {PNS}\n"
                 "theorem clean : True := by trivial\n" + f"end {PNS}\n")
    _write_proof(tmp_path, "holey",
                 "import Mathlib\n" + f"import {PNS}.proofs.L_gone\n"
                 + f"namespace {PNS}\n"
                 "theorem holey (n : Nat) : True := by\n"
                 "  have := gone\n  trivial\n" + f"end {PNS}\n")
    rows = [r for r in db.library_decls_for(conn, "p")
            if r["target_file"] == tf and r["lifecycle"] == "classified"]
    rows.sort(key=lambda r: r["file_order"])
    text, holes, _asm = lib._mechanical_migrate_file(
        conn, problem="p", workspace=tmp_path, target_file=tf,
        target_module="Library.P.Foo", rows=rows)
    assert text is not None
    assert holes == ["holey"]
    assert "theorem clean : True := by trivial" in text   # clean intact
    assert "theorem holey (n : Nat) : True :=" in text     # sig seeded
    assert "sorry" in text
    assert "gone" not in text                              # body dropped
    # all N decls present in order → positional pairing holds
    decls = lib.extract_decls(text)
    assert [d.name for d in decls] == ["clean", "holey"]


def test_context_md_marks_holes_in_seed_mode(conn, tmp_path):
    # compile_librarian_context(holes=[...]) emits the seed banner + marks
    # the hole decl; holes=None (cold) emits neither.
    tf = "Library/P/Foo.lean"
    _seed_classified(conn, "a", "True", tf, 0)
    _seed_classified(conn, "b", "True", tf, 1)
    attempts = tmp_path / ".attempts"
    attempts.mkdir()
    ctx = lib.compile_librarian_context(
        conn, problem="p", work_kind="migrate", attempts_dir=attempts,
        workspace=tmp_path, target_file=tf, holes=["b"])
    body = ctx.read_text(encoding="utf-8")
    assert "finish it, don't rewrite" in body
    assert "HOLE" in body
    # cold (holes=None) → no seed banner
    ctx2 = lib.compile_librarian_context(
        conn, problem="p", work_kind="migrate", attempts_dir=attempts,
        workspace=tmp_path, target_file=tf, holes=None)
    assert "finish it, don't rewrite" not in ctx2.read_text(encoding="utf-8")


def test_context_md_solo_hole_scopes_to_one(conn, tmp_path):
    # Incremental per-decl mode (#87): with solo_hole set, the banner scopes
    # the agent to finishing exactly that one declaration; only the solo hole
    # is tagged FILL THIS, and the other decl carries no ⛏ tag (it is an
    # imported sibling, not an in-seed hole).
    tf = "Library/P/Foo.lean"
    _seed_classified(conn, "a", "True", tf, 0)
    _seed_classified(conn, "b", "True", tf, 1)
    attempts = tmp_path / ".attempts"
    attempts.mkdir()
    ctx = lib.compile_librarian_context(
        conn, problem="p", work_kind="migrate", attempts_dir=attempts,
        workspace=tmp_path, target_file=tf, holes=["a", "b"], solo_hole="a")
    body = ctx.read_text(encoding="utf-8")
    assert "Finish exactly that one declaration" in body
    assert "Finish one declaration" in body
    assert "### 1. `a` ⛏ FILL THIS" in body
    assert "### 2. `b`\n" in body          # other decl: no ⛏ tag
    assert "filled in parallel" not in body


# --- _MechAssembly / _reassemble: the per-hole merge foundation (#87) ---

def test_reassemble_roundtrip_and_override():
    asm = lib._MechAssembly(
        header="import Mathlib",
        target_module="Library.P.Foo",
        slugs=["a", "b", "c"],
        chunks={"a": "theorem a : True := trivial",
                "b": "theorem b : True := by sorry",
                "c": "theorem c : True := trivial"})
    # No override reproduces a deterministic whole file, holes intact, in order.
    full = lib._reassemble(asm)
    assert "namespace Library.P.Foo" in full and "end Library.P.Foo" in full
    assert "theorem b : True := by sorry" in full
    assert full.index("theorem a") < full.index("theorem b") < full.index("theorem c")
    # Overriding b's chunk (a per-hole fill) swaps ONLY b; a/c untouched, order kept.
    merged = lib._reassemble(asm, {"b": "theorem b : True := by exact trivial"})
    assert "theorem b : True := by exact trivial" in merged
    assert "sorry" not in merged
    assert "theorem a : True := trivial" in merged
    assert (merged.index("theorem a") < merged.index("theorem b")
            < merged.index("theorem c"))


# --- incremental per-decl migrate: extraction + orchestration (#87) ---

def _asm3(hole="b"):
    """3-decl assembly a,b,c with `hole` seeded as a `sorry` stub."""
    chunks = {"a": "theorem a : True := trivial",
              "b": "theorem b (n : Nat) : True := trivial",
              "c": "theorem c : True := trivial"}
    chunks[hole] = f"theorem {hole} : True := by sorry"
    return lib._MechAssembly(header="import Mathlib",
                             target_module="Library.P.Foo",
                             slugs=["a", "b", "c"], chunks=chunks)


def test_extract_single_decl_splits_imports_and_body():
    # The incremental seed is `import … + namespace + ONE decl + end`; the
    # decl is alone in the namespace body, so extraction is exact (no anchors).
    text = ("import Mathlib\nimport Library.P.Dep\n"
            "namespace Library.P.Foo\n"
            "theorem b : True := by exact trivial\n"
            "end Library.P.Foo\n")
    chunk, imports = lib._extract_single_decl(text, "Library.P.Foo")
    assert chunk == "theorem b : True := by exact trivial"
    assert "import Mathlib" in imports and "import Library.P.Dep" in imports


def test_merge_header_folds_new_imports_dedup():
    h = "import Mathlib\nimport Library.P.A\n\nopen Matrix"
    merged = lib._merge_header(h, {"import Library.P.B", "import Mathlib"})
    assert merged.count("import Mathlib") == 1            # de-duplicated
    assert "import Library.P.B" in merged                 # new import folded in
    assert "open Matrix" in merged                        # open preserved


def test_hole_still_unfilled_detects_sorry_and_noop():
    seed = "theorem b : True := by sorry"
    assert lib._hole_still_unfilled(seed, seed) is True          # untouched
    assert lib._hole_still_unfilled("theorem b := by sorry", seed) is True
    assert lib._hole_still_unfilled("theorem b : True := trivial", seed) is False


def _inc_kwargs(conn, tmp_path, asm, holes):
    return dict(
        conn=conn, problem="p", workspace=tmp_path, pipeline_id="pid",
        target_file="Library/P/Foo.lean",
        target_path=tmp_path / "Library/P/Foo.lean",
        target_module="Library.P.Foo",
        ordered_slugs=asm.slugs, defs_names=[], whitelist=None,
        attempts_dir=tmp_path / ".attempts", problem_dir=tmp_path / "Problems/p",
        prompt_path=tmp_path / "migrate.md", holes=holes, mech_asm=asm)


def test_incremental_mechanical_and_filled_commit(conn, tmp_path, monkeypatch):
    # a, c relabel mechanically; b is filled by the (mocked) per-decl spawn.
    # The final file carries all three in order, no sorry, committed once.
    asm = _asm3("b")
    captured = {}
    monkeypatch.setattr(lib, "file_dependency_graph", lambda *a, **k: {})

    def fake_commit(merged, **kw):
        captured["merged"] = merged
        return PipelineResult(outcome="success")
    monkeypatch.setattr(lib, "_commit_migrated_file", fake_commit)

    res = lib._migrate_file_incremental(
        **_inc_kwargs(conn, tmp_path, asm, ["b"]),
        fill_fn=lambda slug: ((f"theorem {slug} : True := by exact trivial", []),
                              None),
        olean_writer=lambda p: (True, ""))
    assert res.outcome == "success"
    merged = captured["merged"]
    assert "sorry" not in merged
    assert "theorem b : True := by exact trivial" in merged
    assert "theorem a : True := trivial" in merged       # mechanical untouched
    assert "theorem c : True := trivial" in merged
    assert (merged.index("theorem a") < merged.index("theorem b")
            < merged.index("theorem c"))


def test_incremental_unfilled_is_distinct_no_sorry_failure(
        conn, tmp_path, monkeypatch):
    # The LLM decl can't be filled (spawn exhausted → (None, None)). Result is
    # a DISTINCT no-sorry failure (escalation hook); commit never runs; the
    # partial staging write is cleaned up.
    asm = _asm3("b")
    monkeypatch.setattr(lib, "file_dependency_graph", lambda *a, **k: {})
    monkeypatch.setattr(lib, "_commit_migrated_file",
                        lambda *a, **k: pytest.fail("commit must not run"))

    res = lib._migrate_file_incremental(
        **_inc_kwargs(conn, tmp_path, asm, ["b"]),
        fill_fn=lambda slug: (None, None), olean_writer=lambda p: (True, ""))
    assert res.outcome == "failed"
    assert res.failure_reason == "librarian_migrate_hole_unfilled"
    assert "b" in res.failure_detail and "Strategist" in res.failure_detail
    assert not (tmp_path / "Library/P/Foo.lean").exists()   # partial removed


def test_incremental_decline_routes_to_cascade(conn, tmp_path, monkeypatch):
    # The decl agent emits `-- decline: needs-upstream ...` → routed through
    # the shared cascade on the main conn.
    asm = _asm3("b")
    seen = {}
    monkeypatch.setattr(lib, "file_dependency_graph", lambda *a, **k: {})

    def fake_reopen(conn, **kw):
        seen["patch"] = kw["patch_text"]
        return PipelineResult(outcome="agent_declined",
                              failure_reason="librarian_needs_upstream")
    monkeypatch.setattr(lib, "_decline_or_reopen", fake_reopen)
    monkeypatch.setattr(lib, "_commit_migrated_file",
                        lambda *a, **k: pytest.fail("commit must not run"))

    decline = "-- decline: needs-upstream foo needs a stronger shape\n"
    res = lib._migrate_file_incremental(
        **_inc_kwargs(conn, tmp_path, asm, ["b"]),
        fill_fn=lambda slug: (None, decline), olean_writer=lambda p: (True, ""))
    assert res.failure_reason == "librarian_needs_upstream"
    assert "needs-upstream" in seen["patch"]


def test_incremental_prior_build_fail_is_integrity(conn, tmp_path, monkeypatch):
    # Staging the prior decls fails to build (olean writer says no) before the
    # LLM decl is even spawned → loud integrity failure, fill never runs.
    asm = _asm3("b")
    monkeypatch.setattr(lib, "file_dependency_graph", lambda *a, **k: {})
    monkeypatch.setattr(lib, "_commit_migrated_file",
                        lambda *a, **k: pytest.fail("commit must not run"))

    def fill_must_not_run(slug):
        pytest.fail("fill must not run when priors don't build")
    res = lib._migrate_file_incremental(
        **_inc_kwargs(conn, tmp_path, asm, ["b"]),
        fill_fn=fill_must_not_run, olean_writer=lambda p: (False, "boom"))
    assert res.outcome == "failed"
    assert res.failure_reason == "librarian_integrity_error"
    assert not (tmp_path / "Library/P/Foo.lean").exists()


def test_demote_to_hole_sorry_ifies_body():
    seed = lib._demote_to_hole("theorem b (n : Nat) : True := by exact trivial",
                               "Library.P.Foo")
    assert seed is not None
    assert "theorem b (n : Nat) : True" in seed   # signature kept
    assert "sorry" in seed                         # body replaced
    assert "exact trivial" not in seed             # original body dropped


def test_incremental_localize_demotes_breaking_mechanical_decl(
        conn, tmp_path, monkeypatch):
    # path 2 incremental-ised: a 0-hole assembly (all mechanical) is routed
    # with localize=True. Decl `b`'s mechanical relabel breaks the build, so
    # it is demoted to a per-decl LLM fill; `a`/`c` (which build) are kept.
    asm = lib._MechAssembly(
        header="import Mathlib", target_module="Library.P.Foo",
        slugs=["a", "b", "c"],
        chunks={"a": "theorem a : True := trivial",
                "b": "theorem b : True := bad_relabel",   # breaks the build
                "c": "theorem c : True := trivial"})
    monkeypatch.setattr(lib, "file_dependency_graph", lambda *a, **k: {})
    captured = {}

    def fake_commit(merged, **kw):
        captured["merged"] = merged
        return PipelineResult(outcome="success")
    monkeypatch.setattr(lib, "_commit_migrated_file", fake_commit)

    # The staging build fails iff the partial file still carries the bad body.
    def olw(p):
        return ("bad_relabel" not in p.read_text(encoding="utf-8")), "boom"

    fills = []

    def mock_fill(slug):
        fills.append(slug)
        return (f"theorem {slug} : True := by exact trivial", []), None

    res = lib._migrate_file_incremental(
        **_inc_kwargs(conn, tmp_path, asm, []),
        fill_fn=mock_fill, olean_writer=olw, localize=True)
    assert res.outcome == "success"
    assert fills == ["b"]                       # only the breaker was filled
    assert "bad_relabel" not in captured["merged"]
    assert "sorry" not in captured["merged"]
    assert "theorem a : True := trivial" in captured["merged"]   # kept as-is


# --- unified per-decl source: Defs / root / signature-hole / drift (#87) ---

def _write_defs(tmp_path, body):
    pdir = tmp_path / "Problems" / "p"
    pdir.mkdir(parents=True, exist_ok=True)
    (pdir / "Defs.lean").write_text(body, encoding="utf-8")


def test_defs_decl_migrates_from_defs_lean(conn, tmp_path):
    # A Defs decl (no source goal, no L_<slug>.lean) classified into a file
    # migrates through the SAME mechanical path — its source is its slice of
    # Defs.lean. No hole, no cold from-scratch.
    tf = "Library/P/Defs.lean"
    db.upsert_library_decl(conn, problem="p", slug="MyPred", source_goal_id=None)
    db.set_library_verdict(conn, problem="p", slug="MyPred", verdict="keep")
    db.set_library_classification(conn, problem="p", slug="MyPred",
                                  target_file=tf, target_name=None, file_order=0)
    conn.commit()
    _write_defs(tmp_path,
                "import Mathlib\n" + f"namespace {PNS}\n"
                "def MyPred (n : Nat) : Prop := n = n\n" + f"end {PNS}\n")
    rows = [r for r in db.library_decls_for(conn, "p")
            if r["target_file"] == tf and r["lifecycle"] == "classified"]
    text, holes, _asm = lib._mechanical_migrate_file(
        conn, problem="p", workspace=tmp_path, target_file=tf,
        target_module="Library.P.Defs", rows=rows)
    assert text is not None
    assert holes == []                                   # relabels cleanly
    assert "def MyPred (n : Nat) : Prop := n = n" in text
    assert "namespace Library.P.Defs" in text
    assert "Problems." not in text


def test_defs_decl_preserves_open_header(conn, tmp_path):
    # A Defs decl relying on notation behind an `open` must keep that `open`
    # after migration (else the merged file's Gate A build would fail).
    tf = "Library/P/Defs.lean"
    db.upsert_library_decl(conn, problem="p", slug="MyMat", source_goal_id=None)
    db.set_library_verdict(conn, problem="p", slug="MyMat", verdict="keep")
    db.set_library_classification(conn, problem="p", slug="MyMat",
                                  target_file=tf, target_name=None, file_order=0)
    conn.commit()
    _write_defs(tmp_path,
                "import Mathlib\nopen Matrix\n" + f"namespace {PNS}\n"
                "def MyMat : Nat := 0\n" + f"end {PNS}\n")
    rows = [r for r in db.library_decls_for(conn, "p")
            if r["target_file"] == tf and r["lifecycle"] == "classified"]
    text, holes, _asm = lib._mechanical_migrate_file(
        conn, problem="p", workspace=tmp_path, target_file=tf,
        target_module="Library.P.Defs", rows=rows)
    assert text is not None and holes == []
    assert "open Matrix" in text                 # notation header preserved


def test_root_decl_migrates_from_root_lean(conn, tmp_path):
    # The root theorem's source is Root.lean (its lean_path), not an L_ file.
    # It migrates uniformly — no cold path.
    tf = "Library/P/Main.lean"
    g = db.insert_goal(conn, problem="p", slug="main",
                       lean_path="Problems/p/Root.lean", statement="True",
                       origin="root", kind="theorem")
    conn.execute("UPDATE goals SET status='proved' WHERE id=?", (g,))
    db.upsert_library_decl(conn, problem="p", slug="main", source_goal_id=g)
    db.set_library_verdict(conn, problem="p", slug="main", verdict="keep")
    db.set_library_classification(conn, problem="p", slug="main",
                                  target_file=tf, target_name=None, file_order=0)
    conn.commit()
    pdir = tmp_path / "Problems" / "p"
    pdir.mkdir(parents=True, exist_ok=True)
    (pdir / "Root.lean").write_text(
        "import Mathlib\n" + f"namespace {PNS}\n"
        "theorem main : True := by trivial\n" + f"end {PNS}\n",
        encoding="utf-8")
    rows = [r for r in db.library_decls_for(conn, "p")
            if r["target_file"] == tf and r["lifecycle"] == "classified"]
    text, holes, _asm = lib._mechanical_migrate_file(
        conn, problem="p", workspace=tmp_path, target_file=tf,
        target_module="Library.P.Main", rows=rows)
    assert text is not None
    assert holes == []
    assert "theorem main : True := by trivial" in text
    assert "namespace Library.P.Main" in text


def test_signature_hole_when_sig_cites_unmigrated_defs(conn, tmp_path):
    # `foo`'s SIGNATURE references a Defs symbol `MyT` with no migrated
    # Library module → not even body_to_sorry is Defs-free → best-effort
    # SIGNATURE hole (NOT a cold from-scratch spawn). The unresolved ref is
    # left in the seed for the per-hole LLM to restate.
    tf = "Library/P/Foo.lean"
    _seed_classified(conn, "foo", "True", tf, 0)
    _write_defs(tmp_path,
                "import Mathlib\n" + f"namespace {PNS}\n"
                "def MyT : Type := Nat\n" + f"end {PNS}\n")
    _write_proof(tmp_path, "foo",
                 "import Mathlib\n" + f"import {PNS}.Defs\n"
                 + f"namespace {PNS}\n"
                 "theorem foo (x : MyT) : True := by trivial\n"
                 + f"end {PNS}\n")
    rows = [r for r in db.library_decls_for(conn, "p")
            if r["target_file"] == tf and r["lifecycle"] == "classified"]
    text, holes, _asm = lib._mechanical_migrate_file(
        conn, problem="p", workspace=tmp_path, target_file=tf,
        target_module="Library.P.Foo", rows=rows)
    assert text is not None                  # NOT None / cold
    assert holes == ["foo"]                  # seeded as a (signature) hole
    assert "sorry" in text
    assert "MyT" in text                     # unresolved sig ref left for LLM


def test_alias_missing_strategy_is_integrity_error(conn, tmp_path):
    # An alias L_ file pointing at a _strategy_s* file that is missing on
    # disk is file↔DB drift → raised loud (never a silent cold spawn).
    tf = "Library/P/Foo.lean"
    _seed_classified(conn, "aliased", "True", tf, 0)
    _write_proof(tmp_path, "aliased",
                 "import Mathlib\n"
                 + f"import {PNS}.proofs._strategy_s9999\n"
                 + f"namespace {PNS}\n"
                 + f"def aliased := @{PNS}.s9999\n"
                 + f"end {PNS}\n")
    rows = [r for r in db.library_decls_for(conn, "p")
            if r["target_file"] == tf and r["lifecycle"] == "classified"]
    with pytest.raises(lib._MechIntegrityError):
        lib._mechanical_migrate_file(
            conn, problem="p", workspace=tmp_path, target_file=tf,
            target_module="Library.P.Foo", rows=rows)


def test_run_migrate_holes_hard_fail_no_llm(conn, tmp_path, monkeypatch):
    # v0.3 (plan §3): a mechanical relabel hole → HARD FAIL, no LLM fallback,
    # no agent spawn. (In v0.2 a hole fell through to a per-decl LLM fill.)
    tf = "Library/P/Foo.lean"
    _seed_classified(conn, "lem_a", "True", tf, 0)
    _write_proof(tmp_path, "lem_a",
                 "import Mathlib\ntheorem lem_a : True := by trivial\n")
    # Force a hole regardless of the real relabel outcome.
    monkeypatch.setattr(lib, "_mechanical_migrate_file",
                        lambda *a, **k: ("seed", ["lem_a"], object()))
    import Tooling.agent as agent

    def _no_spawn(**kw):
        raise AssertionError("v0.3 migrate must not spawn an agent")
    monkeypatch.setattr(agent, "spawn_llm", _no_spawn)

    r = lib._run_migrate(
        conn, problem="p", workspace=tmp_path, pipeline_id="pid",
        target_file=tf, attempts_dir=tmp_path / ".a",
        problem_dir=tmp_path / "Problems" / "p",
        prompt_path=tmp_path / "x.md", whitelist=[])
    assert r.outcome == "failed"
    assert r.failure_reason == "librarian_migrate_not_mechanical"


def test_uses_sorry_ignores_comments():
    # The migrate gate's sorry pre-check must ignore comments — a note like
    # "Builds sorry-free" or a doc-comment mentioning sorry is NOT a real sorry
    # (BT FreeGroupWord false-positive). The kernel axiom probe is authoritative.
    assert lib._uses_sorry("theorem x : True := by sorry")            # real
    assert lib._uses_sorry("theorem x : True := by\n  sorry  -- note")  # real + trailing comment
    assert not lib._uses_sorry("-- Builds sorry-free\ntheorem x : True := trivial")
    assert not lib._uses_sorry("/-- historically used sorry -/\ntheorem x : True := trivial")
    assert not lib._uses_sorry("theorem sorry_free : True := trivial")  # identifier prefix


# ---------------------------------------------------------------------
# Defs-decl extraction: section/variable context (stokes form_coord)
# ---------------------------------------------------------------------

_SECTIONED_DEFS = """import Mathlib

open Foo

namespace Problems.p

variable {a : Type*}

section S

variable [Inhabited a] (x : a)

noncomputable def inSection : a := x

end S

def afterSection : a := default

end Problems.p
"""


def test_defs_decl_source_replays_section_variables():
    # A Defs decl inside `section / variable … / end` loses its binders if
    # sliced alone — auto-bound implicits drop the instance constraints →
    # synthInstanceFailed at migrate build (stokes form_coord 2026-06-11).
    out = lib._defs_decl_source(_SECTIONED_DEFS, "inSection")
    assert "variable {a : Type*}" in out                  # namespace-level
    assert "variable [Inhabited a] (x : a)" in out        # section-level
    assert "noncomputable def inSection" in out
    assert "end S" not in out                             # stray end trimmed
    assert out.index("variable {a") < out.index("variable [Inhabited") \
        < out.index("def inSection")                      # source order


def test_defs_decl_source_scopes_die_at_end():
    # A decl AFTER `end S` must NOT inherit the section's variables.
    out = lib._defs_decl_source(_SECTIONED_DEFS, "afterSection")
    assert "variable {a : Type*}" in out                  # still in scope
    assert "Inhabited" not in out                         # died at `end S`
    assert "def afterSection" in out
    assert "end Problems.p" not in out                    # EOF tail trimmed


def test_defs_decl_source_multiline_variable_block():
    text = ("namespace Problems.p\n\nvariable\n  {E : Type*} [Zero E]\n"
            "  {H : Type*}\n\ndef d : E := 0\n\nend Problems.p\n")
    out = lib._defs_decl_source(text, "d")
    assert "{E : Type*} [Zero E]" in out and "{H : Type*}" in out
    assert out.rstrip().endswith("def d : E := 0")


# ---------------------------------------------------------------------
# cross-problem target_file ownership guard (stokes definition-tower)
# ---------------------------------------------------------------------

def test_run_migrate_refuses_file_owned_by_other_problem(conn, tmp_path):
    # Two problems classified decls into the SAME Library file; the second
    # migrate would clobber the first's committed content (whole-file write).
    # Loud fail instead — merge/layout policy is a design decision.
    tf = "Library/P/Shared.lean"
    _seed_classified(conn, "lem_a", "True", tf, 0)
    # the OTHER problem already migrated into tf
    conn.execute("INSERT INTO problems (name, manifest_path, created_at, "
                 "bootstrap_done) VALUES ('q','',?,1)", (db.now(),))
    conn.commit()
    g = db.insert_goal(conn, problem="q", slug="other",
                       lean_path="Problems/q/proofs/L_other.lean",
                       statement="True", origin="backward", kind="theorem")
    conn.execute("UPDATE goals SET status='proved' WHERE id=?", (g,))
    conn.commit()
    db.upsert_library_decl(conn, problem="q", slug="other", source_goal_id=g)
    db.set_library_verdict(conn, problem="q", slug="other", verdict="keep")
    db.set_library_classification(conn, problem="q", slug="other",
                                  target_file=tf, target_name="Library.P.Shared.other",
                                  file_order=0)
    db.mark_library_migrated(conn, problem="q", slug="other")
    r = lib._run_migrate(
        conn, problem="p", workspace=tmp_path, pipeline_id="pid",
        target_file=tf, attempts_dir=tmp_path / ".a",
        problem_dir=tmp_path / "Problems" / "p",
        prompt_path=tmp_path / "x.md", whitelist=[])
    assert r.outcome == "failed"
    assert r.failure_reason == "librarian_file_owned_by_other"
    assert "q" in r.failure_detail
