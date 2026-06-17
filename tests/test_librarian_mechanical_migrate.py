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


def test_defs_decl_source_local_variable_in_travels_with_its_decl():
    # `variable (n M) in` is a LOCAL re-annotation binding ONLY to the decl
    # immediately after it. It must travel in THAT decl's slice — not be
    # collected as a section-level variable (it starts with the keyword),
    # which left it dangling on the PREVIOUS decl's slice and wrongly
    # prepended it to LATER decls → "redundant binder annotation update" +
    # dangling `variable in` at migrate build (stokes_induced_orient POU,
    # 2026-06-12).
    text = ("namespace Problems.p\n\n"
            "variable {n : Nat} {M : Type*}\n\n"
            "def chartFun (q : M) : Nat := n\n\n"
            "variable (n M) in\n"
            "def pou : Nat := n\n\n"
            "def usePou : Nat := pou n M\n\n"
            "end Problems.p\n")
    # 1. travels with `pou`, after the file-level block, before the decl.
    pou = lib._defs_decl_source(text, "pou")
    assert pou.index("variable {n : Nat}") \
        < pou.index("variable (n M) in") \
        < pou.index("def pou")
    # 2. the PREVIOUS decl's slice has no dangling `variable ... in` tail.
    chartfun = lib._defs_decl_source(text, "chartFun")
    assert "variable (n M) in" not in chartfun
    assert chartfun.rstrip().endswith("def chartFun (q : M) : Nat := n")
    # 3. a LATER decl must NOT inherit the local re-annotation (its n/M stay
    #    implicit) — only the file-level block is replayed.
    usepou = lib._defs_decl_source(text, "usePou")
    assert "variable (n M) in" not in usepou
    assert "variable {n : Nat}" in usepou


def test_defs_decl_source_open_in_travels_with_its_decl():
    # `open Classical in` is a LOCAL scoped open binding ONLY to the decl after
    # it. It must travel in THAT decl's slice — hoisting it to the file-level
    # header dangles a scoped-open above `namespace` → "Missing name after
    # `end`" parse failure (residue_thm windingNumber, 2026-06-17).
    text = ("namespace Complex\n\n"
            "open Classical in\n"
            "noncomputable def windingNumber (a : Nat) : Nat := a\n\n"
            "def other : Nat := 0\n\n"
            "end Complex\n")
    # 1. `open Classical in` travels INTO windingNumber's slice, before the def.
    wn = lib._defs_decl_source(text, "windingNumber")
    assert "open Classical in" in wn
    assert wn.index("open Classical in") < wn.index("def windingNumber")
    # 2. a LATER decl does not inherit the scoped open.
    other = lib._defs_decl_source(text, "other")
    assert "open Classical in" not in other


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


def test_defs_decl_source_docstring_travels_with_decl():
    # decl N+1's docstring sits between decl N and decl N+1 — next-decl-head
    # slicing put it at the TAIL of N's slice, and the per-slice variable
    # replay then separated `/-- doc -/` from its decl → parse error
    # (`unexpected token 'variable'`, stokes bdry_chart 2026-06-11). The
    # docstring must travel in its own decl's slice, AFTER the variables.
    text = ("namespace Problems.p\n\nvariable {n : Nat}\n\n"
            "def first (k : Nat) : Nat := k + n\n\n"
            "/-- doc of second. -/\n"
            "def second : Nat := n\n\nend Problems.p\n")
    first = lib._defs_decl_source(text, "first")
    assert "doc of second" not in first              # not in N's tail
    second = lib._defs_decl_source(text, "second")
    assert second.index("variable {n : Nat}") \
        < second.index("/-- doc of second. -/") \
        < second.index("def second")                 # vars BEFORE the docstring
    # a /-! module docstring above a decl is NOT a decl docstring — no extension
    text2 = ("/-! # title -/\n\ndef d : Nat := 0\n")
    assert "title" not in lib._defs_decl_source(text2, "d")


def test_mechanical_migrate_replays_defs_library_imports(conn, tmp_path):
    # clean-before-cite: a problem's Defs.lean can be a pure re-export shim
    # (import Library.X + open, ZERO own decls). relabel drops every decl's
    # `import Problems.<p>.Defs`, and defs_imports only covers symbols
    # DECLARED here (none) — so the Library imports the proofs relied on
    # transitively must be replayed from Defs.lean itself, else the assembled
    # header has the opens but not the imports → unknown namespace
    # (stokes bdry_chart_topo 2026-06-11).
    tf = "Library/P/User.lean"
    _seed_classified(conn, "lem_a", "True", tf, 0)
    _write_proof(tmp_path, "lem_a",
                 "import Mathlib\nimport Problems.p.Defs\n\n"
                 "namespace Problems.p\n"
                 "theorem lem_a : True := by trivial\n"
                 "end Problems.p\n")
    pdir = tmp_path / "Problems" / "p"
    (pdir / "Defs.lean").write_text(
        "import Mathlib\nimport Library.Q.Shared\n\n"
        "open Library.Q.Shared\n\n"
        "namespace Problems.p\nend Problems.p\n", encoding="utf-8")
    rows = [r for r in db.library_decls_for(conn, "p")
            if r["target_file"] == tf]
    text, holes, _asm = lib._mechanical_migrate_file(
        conn, problem="p", workspace=tmp_path, target_file=tf,
        target_module="Library.P.User", rows=rows)
    assert holes == []
    assert "import Library.Q.Shared" in text     # replayed from Defs.lean


# ---------------------------------------------------------------------
# cross-problem shared-def redirect (clean-before-cite salvage)
# ---------------------------------------------------------------------

_SHARED_DEF = ("import Mathlib\n\nnamespace {ns}\n\n"
               "/-- shared. -/\nnoncomputable def sharedDef (k : Nat) : Nat := k + 1\n\n"
               "end {ns}\n")


def _setup_two_problem_shared(conn, tmp_path, other_def_text=None):
    conn.execute("INSERT INTO problems (name, manifest_path, created_at, "
                 "bootstrap_done) VALUES ('q','',?,1)", (db.now(),))
    conn.commit()
    # q owns the Library copy
    g = db.insert_goal(conn, problem="q", slug="q_lemma",
                       lean_path="Problems/q/proofs/L_q_lemma.lean",
                       statement="True", origin="backward", kind="theorem")
    conn.execute("UPDATE goals SET status='proved' WHERE id=?", (g,))
    conn.commit()
    db.upsert_library_decl(conn, problem="q", slug="sharedDef",
                           source_goal_id=None)
    db.set_library_verdict(conn, problem="q", slug="sharedDef", verdict="keep")
    db.set_library_classification(conn, problem="q", slug="sharedDef",
                                  target_file="Library/Q/Shared.lean",
                                  target_name="Library.Q.Shared.sharedDef",
                                  file_order=0)
    db.mark_library_migrated(conn, problem="q", slug="sharedDef")
    for prob, ns in (("p", "Problems.p"), ("q", "Problems.q")):
        pd = tmp_path / "Problems" / prob
        pd.mkdir(parents=True, exist_ok=True)
        text = _SHARED_DEF.format(ns=ns)
        if prob == "q" and other_def_text:
            text = other_def_text.format(ns=ns)
        (pd / "Defs.lean").write_text(text, encoding="utf-8")
    # p re-declares sharedDef + has one lemma using it
    db.upsert_library_decl(conn, problem="p", slug="sharedDef",
                           source_goal_id=None)
    db.set_library_verdict(conn, problem="p", slug="sharedDef", verdict="keep")
    db.set_library_classification(conn, problem="p", slug="sharedDef",
                                  target_file="Library/P/Mine.lean",
                                  target_name=None, file_order=0)
    _seed_classified(conn, "uses_it", "True", "Library/P/Mine.lean", 1)
    _write_proof(tmp_path, "uses_it",
                 "import Mathlib\nimport Problems.p.Defs\n\n"
                 "namespace Problems.p\n"
                 "theorem uses_it : sharedDef 1 = 2 := rfl\n"
                 "end Problems.p\n")


def test_run_migrate_redirects_verbatim_shared_def(conn, tmp_path, monkeypatch):
    _setup_two_problem_shared(conn, tmp_path)
    captured = {}

    def _fake_commit(text, **kw):
        captured["text"] = text
        captured["slugs"] = kw["ordered_slugs"]
        from Tooling.pipeline import PipelineResult
        return PipelineResult(outcome="success")
    monkeypatch.setattr(lib, "_commit_migrated_file", _fake_commit)
    r = lib._run_migrate(
        conn, problem="p", workspace=tmp_path, pipeline_id="pid",
        target_file="Library/P/Mine.lean", attempts_dir=tmp_path / ".a",
        problem_dir=tmp_path / "Problems" / "p",
        prompt_path=tmp_path / "x.md", whitelist=[])
    assert r.outcome == "success"
    row = next(r2 for r2 in db.library_decls_for(conn, "p")
               if r2["slug"] == "sharedDef")
    assert row["lifecycle"] == "cited"                       # redirected
    assert row["citation"] == "Library.Q.Shared.sharedDef"
    assert captured["slugs"] == ["uses_it"]                  # def NOT emitted
    assert "def sharedDef" not in captured["text"]
    assert "import Library.Q.Shared" in captured["text"]     # cited module in
    assert "open Library.Q.Shared" in captured["text"]


def test_run_migrate_no_redirect_for_different_def(conn, tmp_path, monkeypatch):
    # Same leaf name, DIFFERENT definition → must NOT silently redirect.
    _setup_two_problem_shared(
        conn, tmp_path,
        other_def_text=("import Mathlib\n\nnamespace {ns}\n\n"
                        "noncomputable def sharedDef (k : Nat) : Nat := k + 2\n\n"
                        "end {ns}\n"))
    captured = {}

    def _fake_commit(text, **kw):
        captured["text"] = text
        captured["slugs"] = kw["ordered_slugs"]
        from Tooling.pipeline import PipelineResult
        return PipelineResult(outcome="success")
    monkeypatch.setattr(lib, "_commit_migrated_file", _fake_commit)
    lib._run_migrate(
        conn, problem="p", workspace=tmp_path, pipeline_id="pid",
        target_file="Library/P/Mine.lean", attempts_dir=tmp_path / ".a",
        problem_dir=tmp_path / "Problems" / "p",
        prompt_path=tmp_path / "x.md", whitelist=[])
    row = next(r2 for r2 in db.library_decls_for(conn, "p")
               if r2["slug"] == "sharedDef")
    assert row["lifecycle"] != "cited"                       # NOT redirected
    assert "sharedDef" in captured["slugs"]                  # emits its OWN copy
    assert "def sharedDef" in captured["text"]


def test_code_normalized_strips_comments():
    a = "/-- doc A. -/\nnoncomputable def f (k : Nat) : Nat := k + 1  -- note"
    b = "/-- different doc B, extra sentence. -/\nnoncomputable def f (k : Nat) : Nat := k + 1"
    assert lib._code_normalized(a) == lib._code_normalized(b)
    c = "noncomputable def f (k : Nat) : Nat := k + 2"
    assert lib._code_normalized(a) != lib._code_normalized(c)


def test_run_migrate_redirects_despite_docstring_diff(conn, tmp_path,
                                                      monkeypatch):
    # The 同源 check must compare CODE only — the three form_coord problems'
    # Defs carry differently-worded docstrings for the byte-same def (self
    # missed the redirect and emitted a duplicate, live 2026-06-11).
    _setup_two_problem_shared(
        conn, tmp_path,
        other_def_text=("import Mathlib\n\nnamespace {ns}\n\n"
                        "/-- TOTALLY different wording. -/\n"
                        "noncomputable def sharedDef (k : Nat) : Nat := k + 1\n\n"
                        "end {ns}\n"))
    captured = {}

    def _fake_commit(text, **kw):
        captured["slugs"] = kw["ordered_slugs"]
        from Tooling.pipeline import PipelineResult
        return PipelineResult(outcome="success")
    monkeypatch.setattr(lib, "_commit_migrated_file", _fake_commit)
    lib._run_migrate(
        conn, problem="p", workspace=tmp_path, pipeline_id="pid",
        target_file="Library/P/Mine.lean", attempts_dir=tmp_path / ".a",
        problem_dir=tmp_path / "Problems" / "p",
        prompt_path=tmp_path / "x.md", whitelist=[])
    row = next(r2 for r2 in db.library_decls_for(conn, "p")
               if r2["slug"] == "sharedDef")
    assert row["lifecycle"] == "cited"            # redirected despite doc diff
    assert captured["slugs"] == ["uses_it"]


def test_inject_heartbeat_options_after_imports():
    t = "import Mathlib\nimport Library.Q.X\n\nopen Foo\n\ntheorem a : True := trivial\n"
    out = lib._inject_heartbeat_options(t)
    ls = out.splitlines()
    assert ls[2] == ""
    assert ls[3] == "set_option maxHeartbeats 800000"
    assert ls[4] == "set_option synthInstance.maxHeartbeats 400000"
    assert lib._inject_heartbeat_options(out) == out      # idempotent


def test_run_migrate_heartbeat_rung(conn, tmp_path, monkeypatch):
    # Standalone-green decls can time out typeclass synthesis in the MERGED
    # environment (Defs scoped-opens replay; stokes form_bundle 2026-06-11).
    # A 'heartbeats' build failure must retry once with the budget options
    # injected — and succeed without burning the unit.
    tf = "Library/P/Heavy.lean"
    _seed_classified(conn, "lem_a", "True", tf, 0)
    _write_proof(tmp_path, "lem_a",
                 "import Mathlib\nimport Problems.p.Defs\n\n"
                 "namespace Problems.p\n"
                 "theorem lem_a : True := by trivial\n"
                 "end Problems.p\n")
    (tmp_path / "Problems" / "p" / "Defs.lean").write_text(
        "import Mathlib\nnamespace Problems.p\nend Problems.p\n",
        encoding="utf-8")
    calls = []

    def _fake_commit(text, **kw):
        calls.append(text)
        from Tooling.pipeline import PipelineResult
        if "synthInstance.maxHeartbeats" not in text:
            return PipelineResult(
                outcome="failed", failure_reason="librarian_gate_failed",
                failure_detail="(deterministic) timeout at typeclass, maximum "
                               "number of heartbeats (20000) has been reached")
        return PipelineResult(outcome="success")
    monkeypatch.setattr(lib, "_commit_migrated_file", _fake_commit)
    r = lib._run_migrate(
        conn, problem="p", workspace=tmp_path, pipeline_id="pid",
        target_file=tf, attempts_dir=tmp_path / ".a",
        problem_dir=tmp_path / "Problems" / "p",
        prompt_path=tmp_path / "x.md", whitelist=[])
    assert r.outcome == "success"
    assert len(calls) == 2                       # plain, then bumped
    assert "set_option synthInstance.maxHeartbeats 400000" in calls[1]


# ---------------------------------------------------------------------
# @[instance] attribute carry-through (instance-Root feature, 36021a0)
# ---------------------------------------------------------------------

def test_extract_decls_tolerates_attr_prefix():
    text = ("namespace Library.P.F\n"
            "@[instance] theorem foo : True := trivial\n"
            "@[simp]\n"
            "theorem bar : True := trivial\n"
            "end Library.P.F\n")
    decls = lib.extract_decls(text)
    assert [d.name for d in decls] == ["foo", "bar"]


def test_inline_alias_carries_instance_attr(tmp_path):
    from Tooling.quality.librarian import relabel
    alias = ("import Mathlib\n"
             "import Problems.p.proofs._strategy_s11\n"
             "namespace Problems.p\n"
             "@[instance] def main := @Problems.p.proofs.s11\n"
             "end Problems.p\n")
    strategy = ("import Mathlib\n"
                "namespace Problems.p\n"
                "theorem s11 : Nonempty Nat := ⟨0⟩\n"
                "end Problems.p\n")
    res = relabel.inline_alias(
        alias, strategy, slug="main",
        problem_namespace="Problems.p",
        target_namespace="Library.P.F", keep_slugs={"main"})
    assert res.ok
    lines = res.text.splitlines()
    i = next(k for k, l in enumerate(lines) if "theorem main" in l)
    assert lines[i - 1].strip() == "@[instance]"      # attr re-attached
    # plain alias (no attr): byte-identical behavior, no spurious attr
    res2 = relabel.inline_alias(
        alias.replace("@[instance] ", ""), strategy, slug="main",
        problem_namespace="Problems.p",
        target_namespace="Library.P.F", keep_slugs={"main"})
    assert res2.ok and "@[instance]" not in res2.text


def test_defs_decl_source_carries_standalone_attr_line():
    text = ("namespace Problems.p\n\nvariable {n : Nat}\n\n"
            "@[instance]\ntheorem instFoo : Nonempty Nat := ⟨n⟩\n\n"
            "def after : Nat := 0\n\nend Problems.p\n")
    out = lib._defs_decl_source(text, "instFoo")
    assert "@[instance]" in out
    assert out.index("variable") < out.index("@[instance]") \
        < out.index("theorem instFoo")
    after = lib._defs_decl_source(text, "after")
    assert "@[instance]" not in after                 # stays with instFoo


def test_extract_decls_dotted_namespace_extension():
    # `def DiffForm.integral` (namespace-extension decl) must extract WHOLE —
    # truncating at the dot made the axiom probe reference the nonexistent
    # constant `…StokesIntegralDefs.DiffForm` (stokes_integral 2026-06-12).
    text = ("namespace Library.G.M\n"
            "noncomputable def DiffForm.integral (x : Nat) : Nat := x\n"
            "theorem DiffForm.integral_zero : True := trivial\n"
            "end Library.G.M\n")
    decls = lib.extract_decls(text)
    assert [d.name for d in decls] == ["DiffForm.integral",
                                       "DiffForm.integral_zero"]
    assert decls[0].fq_name == "Library.G.M.DiffForm.integral"


def test_gate_d_nominal_verbatim_special_case(tmp_path):
    # A class/structure Defs decl cannot be rfl-equated; Gate D passes it iff
    # the migrated source is verbatim-equal to the Defs source (normalized,
    # modulo namespace qualification) — stokes_integral OrientedManifold.
    pd = tmp_path / "Problems" / "p"
    pd.mkdir(parents=True)
    (pd / "Defs.lean").write_text(
        "import Mathlib\nnamespace Problems.p\n"
        "/-- doc -/\n"
        "class Orient (N : Type*) where\n"
        "  /-- field doc -/\n"
        "  refForm : N\n"
        "  refForm_ne : refForm = refForm\n\n"
        "def other : Nat := 0\n"
        "end Problems.p\n", encoding="utf-8")
    patch = ("import Mathlib\nnamespace Library.T.F\n"
             "class Orient (N : Type*) where\n"
             "  refForm : N\n"
             "  refForm_ne : refForm = refForm\n\n"
             "end Library.T.F\n")
    kw = dict(problem="p", target_slug="Orient", defs_decls=["Orient"],
              target_module="Library.T.F", kind="class", workspace=tmp_path)
    assert lib.migrate_defeq_gate(patch, **kw).ok          # docstring diff ok
    bad = patch.replace("refForm_ne : refForm = refForm",
                        "refForm_ne : refForm ≠ refForm")  # tampered field
    res = lib.migrate_defeq_gate(bad, **kw)
    assert not res.ok and "verbatim" in res.detail
    # no workspace → still declines (no silent pass)
    kw2 = dict(kw, workspace=None)
    assert not lib.migrate_defeq_gate(patch, **kw2).ok


def test_gate_d_def_verbatim_fallback_after_rfl_failure(tmp_path):
    # A def whose signature mentions a nominal Defs sibling can never be
    # rfl-defeq across the boundary (Problems vs Library copies of the class
    # are distinct declarations) — verbatim source equality is the fallback
    # (stokes_integral DiffForm.integral, 2026-06-12). Tampered body fails both.
    pd = tmp_path / "Problems" / "p"
    pd.mkdir(parents=True)
    (pd / "Defs.lean").write_text(
        "import Mathlib\nnamespace Problems.p\n"
        "class Orient (N : Type*) where\n  ref : N\n\n"
        "noncomputable def total [Orient Nat] : Nat := 7\n"
        "end Problems.p\n", encoding="utf-8")
    patch = ("import Mathlib\nnamespace Library.T.F\n"
             "class Orient (N : Type*) where\n  ref : N\n\n"
             "noncomputable def total [Orient Nat] : Nat := 7\n"
             "end Library.T.F\n")
    failv = lambda probe: (False, "Type mismatch")
    kw = dict(problem="p", target_slug="total", defs_decls=["Orient", "total"],
              target_module="Library.T.F", kind="def", workspace=tmp_path,
              defeq_verifier=failv)
    assert lib.migrate_defeq_gate(patch, **kw).ok
    bad = patch.replace(": Nat := 7", ": Nat := 8")
    assert not lib.migrate_defeq_gate(bad, **kw).ok
    # rfl success path unchanged (verifier ok → no verbatim needed)
    okv = lambda probe: (True, "")
    assert lib.migrate_defeq_gate(bad, **dict(kw, defeq_verifier=okv)).ok
