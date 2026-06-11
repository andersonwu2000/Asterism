"""Token-aware reference rewrite for PHASE 3 cleanup-dedup v1a (task #109)."""
from __future__ import annotations

from Tooling.quality.librarian import dedup
from Tooling.quality.librarian.cleanup import _common as cl_common
from Tooling.quality.librarian.cleanup import decide as cl_decide
from Tooling.quality.librarian.cleanup import mechanical as cl_mechanical
from Tooling.quality.librarian.cleanup import polish as cl_polish
from Tooling.quality.librarian.cleanup import simplify as cl_simplify


# ---------------------------------------------------------------------
# replace_token — whole-token, code-only
# ---------------------------------------------------------------------

def test_replace_bare_whole_token() -> None:
    out, n = dedup.replace_token("foo bar foo baz", "foo", "Q")
    assert out == "Q bar Q baz"
    assert n == 2


def test_replace_does_not_touch_substrings() -> None:
    out, n = dedup.replace_token("foobar foo barfoo", "foo", "Q")
    assert out == "foobar Q barfoo"
    assert n == 1


def test_bare_does_not_match_fqn_tail_or_projection() -> None:
    # `A.foo` (FQN tail / field projection) must NOT match a bare `foo`.
    out, n = dedup.replace_token("A.foo foo X.Y.foo", "foo", "Q")
    assert out == "A.foo Q X.Y.foo"
    assert n == 1


def test_replace_full_fqn() -> None:
    out, n = dedup.replace_token(
        "Library.A.foo (x)\n  Library.A.foo", "Library.A.foo", "Library.B.bar")
    assert out == "Library.B.bar (x)\n  Library.B.bar"
    assert n == 2


def test_fqn_projection_rewrites_longer_name_guarded() -> None:
    # SPEC CHANGE (stokes bdry_manifold 2026-06-11): `Library.A.foo.comp` IS
    # dot-notation projection on the decl being renamed — it must rewrite to
    # `Library.B.bar.comp` (the old name ceases to exist; leaving it dangles).
    out, n = dedup.replace_token("Library.A.foo.comp", "Library.A.foo",
                                 "Library.B.bar")
    assert out == "Library.B.bar.comp" and n == 1
    # what the old test actually guarded — a LONGER identifier — still holds:
    out, n = dedup.replace_token("Library.A.foox", "Library.A.foo", "B")
    assert out == "Library.A.foox" and n == 0


def test_skips_line_comment() -> None:
    out, n = dedup.replace_token("-- foo here\nfoo", "foo", "Q")
    assert out == "-- foo here\nQ"
    assert n == 1


def test_skips_block_and_doc_comment() -> None:
    out, n = dedup.replace_token("/- foo -/ foo /-- foo -/ foo", "foo", "Q")
    # both comment `foo`s preserved; both code `foo`s replaced
    assert out == "/- foo -/ Q /-- foo -/ Q"
    assert n == 2


def test_nested_block_comment() -> None:
    out, n = dedup.replace_token("/- a /- foo -/ b -/ foo", "foo", "Q")
    assert out == "/- a /- foo -/ b -/ Q"
    assert n == 1


def test_no_match_returns_zero() -> None:
    out, n = dedup.replace_token("alpha beta", "foo", "Q")
    assert out == "alpha beta"
    assert n == 0


def test_apostrophe_in_identifier_is_a_boundary_char() -> None:
    # Lean identifiers allow trailing `'`; `foo'` must not match `foo`.
    out, n = dedup.replace_token("foo' foo", "foo", "Q")
    assert out == "foo' Q"
    assert n == 1


# ---------------------------------------------------------------------
# _code_spans
# ---------------------------------------------------------------------

def test_sig_to_forall_simple() -> None:
    assert dedup.sig_to_forall("(x : Nat) : x = x") == "∀ (x : Nat), x = x"


def test_sig_to_forall_no_binders() -> None:
    assert dedup.sig_to_forall(": True") == "True"


def test_sig_to_forall_implicit_and_instance_binders() -> None:
    sig = "{E : Type*} [Inhabited E] (x : E) : x = x"
    assert dedup.sig_to_forall(sig) == "∀ {E : Type*} [Inhabited E] (x : E), x = x"


def test_sig_to_forall_conclusion_colon_not_missplit() -> None:
    # Regression: a conclusion `∃ x : E, …` has its OWN depth-0 colon. The
    # split must be at the TYPE colon (first depth-0), not the last — else
    # the type mangles to `∀ … ∃ x, E, …` ("unexpected type ascription").
    sig = "(U : S) (h : P) : ∃ x : E, x ∈ U"
    assert dedup.sig_to_forall(sig) == "∀ (U : S) (h : P), ∃ x : E, x ∈ U"


def test_type_colon_pos_skips_bracketed_colons() -> None:
    # binder colons are bracketed (depth>0); the type colon is the first
    # depth-0 one.
    assert dedup._type_colon_pos("(x : T) : C") == 8
    assert dedup._type_colon_pos("{a : A} [b : B] : C") == 16


def test_code_spans_partition_round_trips() -> None:
    text = "code1 -- c\ncode2 /- b -/ code3"
    spans = cl_common._code_spans(text)
    # concatenating the code spans + the gaps must reconstruct the text
    assert spans[0][0] == 0
    assert spans[-1][1] == len(text)
    # code spans never overlap a comment marker's interior
    for s, e in spans:
        assert "-- " not in text[s:e]


# ---------------------------------------------------------------------
# proof simplification — (c) per-decl, marked-only, session-retry (P2b)
# ---------------------------------------------------------------------

_FILE2 = ("import Mathlib\n"
          "theorem foo : True := by trivial\n"
          "theorem bar : True := by trivial\n")


def _decl(name, module="Library.P.F", rel="Library/P/F.lean"):
    return dedup._Decl(fqn=f"{module}.{name}", rel=rel, module=module,
                       name=name, sig=f"{name} : True", binders=0,
                       concl_tokens=frozenset())


def _setup_simplify(tmp_path, rel, content, *, prompt="decl_simplify.md"):
    if prompt:
        pd = tmp_path / "Tooling" / "prompts" / "librarian"
        pd.mkdir(parents=True, exist_ok=True)
        (pd / prompt).write_text("simplify", encoding="utf-8")
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def _fake_simplify_spawn(monkeypatch, responses):
    """Patch agent.spawn_llm to write responses[i] (str|None) as simplified.txt."""
    from Tooling import agent
    calls = {"n": 0}

    def _spawn(*, kind, prompt_path, problem_dir, attempts_dir, session_id):
        i = calls["n"]
        calls["n"] += 1
        r = responses[i] if i < len(responses) else None
        if r is not None:
            (attempts_dir / "simplified.txt").write_text(r, encoding="utf-8")
        return 0
    monkeypatch.setattr(agent, "spawn_llm", _spawn)
    return calls


def test_parse_simplify_marks() -> None:
    assert cl_simplify._parse_simplify_marks('["a","b"]') == {"a", "b"}
    assert cl_simplify._parse_simplify_marks('[{"decl":"a"},{"decl":"b"}]') == {"a", "b"}
    assert cl_simplify._parse_simplify_marks("not json") == set()


def test_simplify_success_replaces_only_marked(tmp_path, monkeypatch) -> None:
    rel = "Library/P/F.lean"
    _setup_simplify(tmp_path, rel, _FILE2)
    _fake_simplify_spawn(monkeypatch, ["by simp"])
    monkeypatch.setattr(cl_common, "_build_decl_isolated", lambda ws, **k: (True, ""))
    n = dedup.decl_cleanup_simplify_file(
        tmp_path, "p", rel, [_decl("foo"), _decl("bar")], {"foo"})
    assert n == 1
    txt = (tmp_path / rel).read_text(encoding="utf-8")
    assert "theorem foo : True := by simp" in txt
    assert "theorem bar : True := by trivial" in txt        # unmarked untouched


def test_simplify_decline_keeps_original(tmp_path, monkeypatch) -> None:
    rel = "Library/P/F.lean"
    _setup_simplify(tmp_path, rel, _FILE2)
    _fake_simplify_spawn(monkeypatch, [None])               # agent produced none
    monkeypatch.setattr(cl_common, "_build_decl_isolated", lambda ws, **k: (True, ""))
    assert dedup.decl_cleanup_simplify_file(
        tmp_path, "p", rel, [_decl("foo")], {"foo"}) == 0
    assert (tmp_path / rel).read_text(encoding="utf-8") == _FILE2


def test_simplify_no_change_skips_build(tmp_path, monkeypatch) -> None:
    rel = "Library/P/F.lean"
    _setup_simplify(tmp_path, rel, _FILE2)
    _fake_simplify_spawn(monkeypatch, ["by trivial"])       # == current proof
    built = {"n": 0}

    def _b(ws, **k):
        built["n"] += 1
        return (True, "")
    monkeypatch.setattr(cl_common, "_build_decl_isolated", _b)
    assert dedup.decl_cleanup_simplify_file(
        tmp_path, "p", rel, [_decl("foo")], {"foo"}) == 0
    assert built["n"] == 0


def test_simplify_build_fail_keeps_original(tmp_path, monkeypatch) -> None:
    rel = "Library/P/F.lean"
    _setup_simplify(tmp_path, rel, _FILE2)
    _fake_simplify_spawn(monkeypatch, ["by simp", "by simp", "by simp"])
    monkeypatch.setattr(cl_common, "_build_decl_isolated",
                        lambda ws, **k: (False, "boom"))
    assert dedup.decl_cleanup_simplify_file(
        tmp_path, "p", rel, [_decl("foo")], {"foo"}, max_retries=2) == 0
    assert (tmp_path / rel).read_text(encoding="utf-8") == _FILE2


def test_simplify_retry_then_success(tmp_path, monkeypatch) -> None:
    rel = "Library/P/F.lean"
    _setup_simplify(tmp_path, rel, _FILE2)
    _fake_simplify_spawn(monkeypatch, ["by bad", "by simp"])
    seq = iter([(False, "err"), (True, "")])
    monkeypatch.setattr(cl_common, "_build_decl_isolated", lambda ws, **k: next(seq))
    assert dedup.decl_cleanup_simplify_file(
        tmp_path, "p", rel, [_decl("foo")], {"foo"}, max_retries=2) == 1
    assert "theorem foo : True := by simp" in (
        tmp_path / rel).read_text(encoding="utf-8")


def test_simplify_noop_when_nothing_marked(tmp_path, monkeypatch) -> None:
    rel = "Library/P/F.lean"
    _setup_simplify(tmp_path, rel, _FILE2)
    calls = _fake_simplify_spawn(monkeypatch, ["by simp"])
    assert dedup.decl_cleanup_simplify_file(
        tmp_path, "p", rel, [_decl("foo")], set()) == 0
    assert calls["n"] == 0                                   # never spawned


def test_mark_simplify_noop_when_prompt_absent(tmp_path, monkeypatch) -> None:
    calls = _fake_simplify_spawn(monkeypatch, [])
    assert cl_simplify._mark_simplify_file(
        tmp_path, "p", "Library/P/F.lean", ["foo"], tmp_path) == set()
    assert calls["n"] == 0


# ---------------------------------------------------------------------
# drop_decl / decl_span
# ---------------------------------------------------------------------

_SAMPLE = (
    "import Mathlib\n\n"
    "namespace Foo\n\n"
    "-- doc for alpha\n"
    "theorem alpha (x : Nat) : x = x := by rfl\n\n"
    "-- doc for beta\n"
    "theorem beta : True := by trivial\n\n"
    "-- doc for gamma\n"
    "theorem gamma (y : Nat) : y = y := by rfl\n\n"
    "end Foo\n"
)


def test_drop_middle_decl_removes_decl_and_its_doc() -> None:
    out, ok = dedup.drop_decl(_SAMPLE, "beta")
    assert ok
    assert "theorem beta" not in out and "doc for beta" not in out
    assert "theorem alpha" in out and "doc for alpha" in out
    assert "theorem gamma" in out and "doc for gamma" in out
    assert "namespace Foo" in out and "end Foo" in out


def test_drop_first_decl() -> None:
    out, ok = dedup.drop_decl(_SAMPLE, "alpha")
    assert ok
    assert "theorem alpha" not in out and "doc for alpha" not in out
    assert "namespace Foo" in out
    assert "theorem beta" in out and "doc for beta" in out


def test_drop_last_decl_stops_at_end() -> None:
    out, ok = dedup.drop_decl(_SAMPLE, "gamma")
    assert ok
    assert "theorem gamma" not in out and "doc for gamma" not in out
    assert "theorem beta" in out and "end Foo" in out


def test_drop_absent_decl_is_noop() -> None:
    out, ok = dedup.drop_decl(_SAMPLE, "zeta")
    assert not ok and out == _SAMPLE


_SAMPLE_BLOCKDOC = (
    "import Mathlib\n\n"
    "namespace Foo\n\n"
    "/-- single-line doc for alpha -/\n"
    "theorem alpha : True := trivial\n\n"
    "/-- multi-line doc\n  for beta -/\n"
    "theorem beta : True := trivial\n\n"
    "end Foo\n"
)


def test_drop_decl_with_single_line_block_doc() -> None:
    # regression: _block_start must treat a self-contained `/-- … -/` as ONE
    # comment line, not the end of a block that swallows everything above it.
    out, ok = dedup.drop_decl(_SAMPLE_BLOCKDOC, "alpha")
    assert ok
    assert "alpha" not in out and "doc for alpha" not in out
    assert "import Mathlib" in out and "namespace Foo" in out  # not over-eaten
    assert "theorem beta" in out and "multi-line doc" in out


def test_drop_decl_with_multi_line_block_doc() -> None:
    out, ok = dedup.drop_decl(_SAMPLE_BLOCKDOC, "beta")
    assert ok
    assert "beta" not in out and "multi-line doc" not in out
    assert "theorem alpha" in out and "single-line doc for alpha" in out


# ---------------------------------------------------------------------
# _external_consumer — cross-problem-consumer safety guard
# ---------------------------------------------------------------------

def _mk_lib(tmp_path, files: dict[str, str]) -> None:
    for rel, content in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")


def _decl(fqn: str) -> "dedup._Decl":
    return dedup._Decl(fqn=fqn, rel="Library/" + "/".join(fqn.split(".")[1:-1])
                       + ".lean", module=fqn.rsplit(".", 1)[0],
                       name=fqn.rsplit(".", 1)[-1], sig=": True",
                       binders=0, concl_tokens=frozenset())


def test_external_consumer_detects_cross_problem_ref(tmp_path) -> None:
    X = _decl("Library.LinearAlgebra.P1.F.foo")
    _mk_lib(tmp_path, {
        X.rel: "import Mathlib\ntheorem foo : True := by trivial\n",
        "Library/LinearAlgebra/P2/G.lean":
            "import Mathlib\nimport Library.LinearAlgebra.P1.F\n"
            "theorem bar : True := by exact foo\n",
    })
    assert dedup._external_consumer(tmp_path, X, {X.rel}) \
        == "Library/LinearAlgebra/P2/G.lean"


def test_external_consumer_detects_fqn_ref(tmp_path) -> None:
    X = _decl("Library.LinearAlgebra.P1.F.foo")
    _mk_lib(tmp_path, {
        X.rel: "import Mathlib\ntheorem foo : True := by trivial\n",
        "Library/LinearAlgebra/P2/G.lean":
            "import Mathlib\ntheorem bar := Library.LinearAlgebra.P1.F.foo\n",
    })
    assert dedup._external_consumer(tmp_path, X, {X.rel}) is not None


def test_external_consumer_none_when_no_cross_ref(tmp_path) -> None:
    X = _decl("Library.LinearAlgebra.P1.F.foo")
    _mk_lib(tmp_path, {
        X.rel: "import Mathlib\ntheorem foo : True := by trivial\n",
        "Library/LinearAlgebra/P2/G.lean":
            "import Mathlib\ntheorem bar : True := by trivial\n",
    })
    assert dedup._external_consumer(tmp_path, X, {X.rel}) is None


def test_external_consumer_ignores_scope_files(tmp_path) -> None:
    # a same-(scope)-problem consumer is NOT "external" (scope rebuild covers it)
    X = _decl("Library.LinearAlgebra.P1.F.foo")
    _mk_lib(tmp_path, {
        X.rel: "import Mathlib\ntheorem foo : True := by trivial\n",
        "Library/LinearAlgebra/P1/H.lean":
            "import Mathlib\nimport Library.LinearAlgebra.P1.F\n"
            "theorem baz : True := by exact foo\n",
    })
    scope = {X.rel, "Library/LinearAlgebra/P1/H.lean"}
    assert dedup._external_consumer(tmp_path, X, scope) is None


# ---------------------------------------------------------------------
# _strip_json_fence (shared by the verdict / simplify parsers)
# ---------------------------------------------------------------------

def test_strip_json_fence_plain() -> None:
    assert cl_common._strip_json_fence('[{"x":"a"}]') == '[{"x":"a"}]'


def test_strip_json_fence_fenced() -> None:
    assert cl_common._strip_json_fence('```json\n[{"x":"a"}]\n```') == '[{"x":"a"}]'
    assert cl_common._strip_json_fence('```\n[]\n```') == '[]'


_INDEX = (
    "## LinearAlgebra.p1\n"
    "- `Library.LinearAlgebra.P1.F.foo` → `Library/LinearAlgebra/P1/F.lean`\n"
    "## LinearAlgebra.p2\n"
    "- `Library.LinearAlgebra.P2.G.bar` → `Library/LinearAlgebra/P2/G.lean`\n"
)


def test_apply_llm_pairs_skips_invalid_without_lake(tmp_path) -> None:
    # x not in SCOPE → skipped; no valid probe pair → lake is never touched.
    _mk_lib(tmp_path, {
        "Library/INDEX.md": _INDEX,
        "Library/LinearAlgebra/P1/F.lean":
            "import Mathlib\ntheorem foo (n : Nat) : n = n := by rfl\n",
        "Library/LinearAlgebra/P2/G.lean":
            "import Mathlib\ntheorem bar (m : Nat) : m = m := by rfl\n",
    })
    # both pairs invalid: first has unknown x, second's x is a POOL (not SCOPE) decl
    res = dedup.apply_llm_pairs(tmp_path, "LinearAlgebra.p1", [
        ("Library.LinearAlgebra.P1.F.nope", "Library.LinearAlgebra.P2.G.bar"),
        ("Library.LinearAlgebra.P2.G.bar", "Library.LinearAlgebra.P1.F.foo"),
    ], apply=True)
    assert res["dropped"] == {} and res["near"] == []
    assert len(res["skipped"]) == 2


# ---------------------------------------------------------------------
# v1b-② — _proof_assign_pos / replace_proof (near-dup proof collapse)
# ---------------------------------------------------------------------

def test_proof_assign_pos_simple() -> None:
    s = "theorem f : T := pf"
    assert s[cl_common._proof_assign_pos(s, 0):][:2] == ":="


def test_proof_assign_pos_skips_binder_default() -> None:
    # the `:=` inside `(x : Nat := 0)` (depth>0) must be skipped; the proof
    # `:=` is the first at depth 0.
    s = "theorem f (x : Nat := 0) : T := pf"
    p = cl_common._proof_assign_pos(s, 0)
    assert s[p:] == ":= pf"


def test_proof_assign_pos_skips_structure_instance() -> None:
    s = "theorem f : T := by exact { a := 1 }"
    p = cl_common._proof_assign_pos(s, 0)
    assert s[p:] == ":= by exact { a := 1 }"   # proof :=, not the inner one


_SAMPLE2 = (
    "import Mathlib\n\n"
    "namespace Foo\n\n"
    "/-- doc for foo -/\n"
    "theorem foo (n : Nat) : n = n := by\n  rfl\n\n"
    "/-- doc for bar -/\n"
    "theorem bar : True := trivial\n\n"
    "end Foo\n"
)


def test_replace_proof_collapses_keeps_signature() -> None:
    out, ok = dedup.replace_proof(_SAMPLE2, "foo", "by simp")
    assert ok
    assert "theorem foo (n : Nat) : n = n := by simp" in out
    assert "rfl" not in out                      # old proof gone
    assert "/-- doc for foo -/" in out           # header/doc kept
    assert "theorem bar : True := trivial" in out  # next decl untouched
    assert "/-- doc for bar -/" in out
    assert "end Foo" in out


def test_replace_proof_term_mode() -> None:
    out, ok = dedup.replace_proof(_SAMPLE2, "bar", "Foo.foo_bridge")
    assert ok
    assert "theorem bar : True := Foo.foo_bridge" in out
    assert "theorem foo (n : Nat) : n = n := by" in out  # foo untouched


def test_replace_proof_absent_is_noop() -> None:
    out, ok = dedup.replace_proof(_SAMPLE2, "zeta", "by simp")
    assert not ok and out == _SAMPLE2


def test_replace_proof_preserves_following_blank_separation() -> None:
    out, _ = dedup.replace_proof(_SAMPLE2, "foo", "by simp")
    # the blank line + next decl's doc block survive the collapse
    assert "by simp\n\n/-- doc for bar -/" in out


def test_decl_proof_body_tactic() -> None:
    assert dedup.decl_proof_body(_SAMPLE2, "foo") == "by\n  rfl"


def test_decl_proof_body_term() -> None:
    assert dedup.decl_proof_body(_SAMPLE2, "bar") == "trivial"


def test_decl_proof_body_absent() -> None:
    assert dedup.decl_proof_body(_SAMPLE2, "zeta") is None


def test_replace_proof_with_moved_body_round_trip() -> None:
    # the wrapper-merge core: move foo's body onto bar
    body = dedup.decl_proof_body(_SAMPLE2, "foo")
    out, ok = dedup.replace_proof(_SAMPLE2, "bar", body)
    assert ok
    assert "theorem bar : True := by\n  rfl" in out


# ---------------------------------------------------------------------
# mathlib-tier — _resolve_y
# ---------------------------------------------------------------------

def test_resolve_y_library_pool_decl() -> None:
    d = _decl("Library.LinearAlgebra.P1.F.foo")
    Y, is_mathlib = dedup._resolve_y({d.fqn: d}, d.fqn)
    assert Y is d and is_mathlib is False


def test_load_decls_scope_index_overrides_index(tmp_path) -> None:
    # in-chain: the problem's own decls aren't in INDEX yet (bridge writes it
    # later); scope comes from the supplied list, pool still from INDEX.
    _mk_lib(tmp_path, {
        "Library/INDEX.md":
            "## LinearAlgebra.other\n"
            "- `Library.LinearAlgebra.O.G.bar` → `Library/LinearAlgebra/O/G.lean`\n",
        "Library/LinearAlgebra/P1/F.lean":
            "import Mathlib\ntheorem foo (n : Nat) : n = n := by rfl\n",
        "Library/LinearAlgebra/O/G.lean":
            "import Mathlib\ntheorem bar (m : Nat) : m = m := by rfl\n",
    })
    scope, pool = dedup._load_decls(
        tmp_path, "LinearAlgebra.p1",
        [("Library.LinearAlgebra.P1.F.foo", "Library/LinearAlgebra/P1/F.lean")])
    assert [d.name for d in scope] == ["foo"]                 # from scope_index
    assert "Library.LinearAlgebra.O.G.bar" in {d.fqn for d in pool}  # from INDEX


def test_resolve_y_mathlib_when_not_in_pool() -> None:
    Y, is_mathlib = dedup._resolve_y({}, "Finset.sum_comm")
    assert is_mathlib is True
    assert Y.fqn == "Finset.sum_comm" and Y.name == "sum_comm"
    assert Y.module == ""        # sentinel: Mathlib imported, no extra import


# ---------------------------------------------------------------------
# thin-wrapper detection — _cited_lemma / find_thin_wrappers
# ---------------------------------------------------------------------

def test_cited_lemma_exact() -> None:
    assert dedup._cited_lemma("by exact Module.End.isNilpotent.restrict h hN") \
        == "Module.End.isNilpotent.restrict"


def test_cited_lemma_apply_and_using() -> None:
    assert dedup._cited_lemma("by apply foo_of_bar <;> assumption") == "foo_of_bar"
    assert dedup._cited_lemma("by simpa [x] using Baz.qux") == "Baz.qux"


def test_cited_lemma_term_mode_head() -> None:
    assert dedup._cited_lemma("Submodule.finrank_le U") == "Submodule.finrank_le"


def test_cited_lemma_automation_is_none() -> None:
    for p in ("by norm_num", "by simp [foo]", "by grind", "by omega",
              "by rfl", "by aesop"):
        assert dedup._cited_lemma(p) is None


def test_find_thin_wrappers(tmp_path) -> None:
    idx = ("## LinearAlgebra.p1\n"
           "- `Library.LinearAlgebra.P1.F.thin_deleg` → `Library/LinearAlgebra/P1/F.lean`\n"
           "- `Library.LinearAlgebra.P1.F.thin_auto` → `Library/LinearAlgebra/P1/F.lean`\n"
           "- `Library.LinearAlgebra.P1.F.fat` → `Library/LinearAlgebra/P1/F.lean`\n")
    _mk_lib(tmp_path, {
        "Library/INDEX.md": idx,
        "Library/LinearAlgebra/P1/F.lean":
            "import Mathlib\n"
            "theorem thin_deleg (n : Nat) : n = n := by exact Nat.refl_dummy n\n\n"
            "theorem thin_auto (n : Nat) : n = n := by norm_num\n\n"
            "theorem fat (n : Nat) : n = n := by\n  have h := 1\n  have k := 2\n  rfl\n",
    })
    rows = dedup.find_thin_wrappers(tmp_path, "LinearAlgebra.p1")
    by_name = {f.rsplit(".", 1)[-1]: (p, c) for f, p, c in rows}
    assert "thin_deleg" in by_name and by_name["thin_deleg"][1] == "Nat.refl_dummy"
    assert "thin_auto" in by_name and by_name["thin_auto"][1] is None
    assert "fat" not in by_name        # multi-line proof → not thin


# ---------------------------------------------------------------------
# per-file audit — parse_verdicts / _audit_pairs
# ---------------------------------------------------------------------

def test_parse_verdicts_ok() -> None:
    txt = ('[{"slug":"foo","verdict":"keep","reason":"genuine"},'
           ' {"slug":"bar","verdict":"cite-mathlib","mathlib_name":"Nat.add_comm"},'
           ' {"slug":"baz","verdict":"merge","canonical":"foo"}]')
    vds, err = dedup.parse_verdicts(txt)
    assert err == ""
    assert vds[0]["verdict"] == "keep" and vds[0]["name"] == ""
    assert vds[1]["name"] == "Nat.add_comm"
    assert vds[2]["verdict"] == "merge" and vds[2]["name"] == "foo"


def test_parse_verdicts_bad_verdict() -> None:
    vds, err = dedup.parse_verdicts('[{"slug":"a","verdict":"nuke"}]')
    assert vds is None and "unknown verdict" in err


def test_parse_verdicts_missing_slug() -> None:
    vds, err = dedup.parse_verdicts('[{"verdict":"keep"}]')
    assert vds is None and "missing" in err


def test_audit_pairs_maps_and_resolves() -> None:
    foo = _decl("Library.LinearAlgebra.P1.F.foo")
    bar = _decl("Library.LinearAlgebra.P1.F.bar")
    baz = _decl("Library.LinearAlgebra.P2.G.baz")
    scope_by_leaf = {"foo": foo, "bar": bar}
    all_by_leaf = {"foo": foo, "bar": bar, "baz": baz}
    vds = [
        {"slug": "foo", "verdict": "keep", "name": ""},
        {"slug": "foo", "verdict": "cite-mathlib", "name": "Submodule.finrank_le"},
        {"slug": "bar", "verdict": "merge", "name": "foo"},        # bare → fqn
        {"slug": "ghost", "verdict": "drop", "name": "X.y"},        # unknown slug → skip
    ]
    pairs = dedup._audit_pairs(vds, scope_by_leaf, all_by_leaf)
    assert ("Library.LinearAlgebra.P1.F.foo", "Submodule.finrank_le") in pairs
    assert ("Library.LinearAlgebra.P1.F.bar", "Library.LinearAlgebra.P1.F.foo") in pairs
    assert len(pairs) == 2        # keep skipped, unknown-slug skipped


# ---------------------------------------------------------------------
# _file_topo_order — bottom-up (deps first), from import lines (§13 3c-1)
# ---------------------------------------------------------------------

def test_file_topo_order_chain_deps_first(tmp_path) -> None:
    base = _decl("Library.LA.P.Base.b")
    mid = _decl("Library.LA.P.Mid.m")
    top = _decl("Library.LA.P.Top.t")
    _mk_lib(tmp_path, {
        base.rel: "import Mathlib\ntheorem b : True := trivial\n",
        mid.rel: f"import Mathlib\nimport {base.module}\n"
                 "theorem m : True := trivial\n",
        top.rel: f"import Mathlib\nimport {mid.module}\n"
                 "theorem t : True := trivial\n",
    })
    # unsorted input → deps strictly before importers
    assert dedup._file_topo_order(tmp_path, [top, mid, base]) \
        == [base.rel, mid.rel, top.rel]


def test_file_topo_order_diamond_and_independent(tmp_path) -> None:
    base = _decl("Library.LA.P.Base.b")
    l = _decl("Library.LA.P.L.l")
    r = _decl("Library.LA.P.R.r")
    top = _decl("Library.LA.P.Top.t")            # imports both L and R
    _mk_lib(tmp_path, {
        base.rel: "import Mathlib\ntheorem b : True := trivial\n",
        l.rel: f"import Mathlib\nimport {base.module}\ntheorem l : True := trivial\n",
        r.rel: f"import Mathlib\nimport {base.module}\ntheorem r : True := trivial\n",
        top.rel: f"import Mathlib\nimport {l.module}\nimport {r.module}\n"
                 "theorem t : True := trivial\n",
    })
    order = dedup._file_topo_order(tmp_path, [top, r, l, base])
    pos = {f: i for i, f in enumerate(order)}
    assert pos[base.rel] < pos[l.rel] < pos[top.rel]   # base first, top last
    assert pos[base.rel] < pos[r.rel] < pos[top.rel]
    assert order[0] == base.rel and order[-1] == top.rel


# ---------------------------------------------------------------------
# _resolve_drop_chains — X→Y→Z drop chains repoint to the final survivor
# ---------------------------------------------------------------------

def _mk_decl_file(tmp_path, rel, names):
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    body = "import Mathlib\n" + "\n".join(
        f"theorem {n} : True := by trivial" for n in names) + "\n"
    p.write_text(body, encoding="utf-8")


def _classify_setup(monkeypatch):
    monkeypatch.setattr(dedup, "batch_defeq",
                        lambda ws, p, probe: [True] * len(probe))
    monkeypatch.setattr(dedup, "_nonscope_library_texts", lambda ws, rels: [])


def test_classify_same_file_trusts_marker_over_survivor(tmp_path, monkeypatch) -> None:
    # Marker: drop the SHORTER-named `aa`, keep the longer `aa_much_longer`.
    # `_survivor` prefers the shorter name (disagrees), but same-file → trust the
    # marker and DROP (Finding A — skipping here lost recall).
    P = "LinearAlgebra.p"
    rel = "Library/LinearAlgebra/P/F.lean"
    mod = "Library.LinearAlgebra.P.F"
    _mk_decl_file(tmp_path, rel, ["aa", "aa_much_longer"])
    _classify_setup(monkeypatch)
    si = [(f"{mod}.aa", rel), (f"{mod}.aa_much_longer", rel)]
    plan, skipped = dedup._classify_pairs(
        tmp_path, P, [(f"{mod}.aa", f"{mod}.aa_much_longer")], scope_index=si)
    assert plan.get(f"{mod}.aa", (None, ""))[1] == "drop"   # dropped, not skipped
    assert skipped == []


def test_classify_cross_file_keeps_deterministic_survivor(tmp_path, monkeypatch) -> None:
    # Same disagreement but CROSS-file: keep the deterministic survivor (skip) so
    # parallel per-file workers stay race-safe.
    P = "LinearAlgebra.p"
    relF = "Library/LinearAlgebra/P/F.lean"
    relG = "Library/LinearAlgebra/P/G.lean"
    mod = "Library.LinearAlgebra.P"
    _mk_decl_file(tmp_path, relF, ["aa"])
    _mk_decl_file(tmp_path, relG, ["aa_much_longer"])
    _classify_setup(monkeypatch)
    si = [(f"{mod}.F.aa", relF), (f"{mod}.G.aa_much_longer", relG)]
    plan, skipped = dedup._classify_pairs(
        tmp_path, P, [(f"{mod}.F.aa", f"{mod}.G.aa_much_longer")], scope_index=si)
    assert plan == {}                                       # skipped (canonical kept)
    assert len(skipped) == 1


def test_classify_drops_when_survivor_agrees(tmp_path, monkeypatch) -> None:
    # Marker drops the LONGER `aa_2`, keeps shorter `aa` — `_survivor` agrees →
    # drop regardless of file (the common, always-worked case).
    P = "LinearAlgebra.p"
    rel = "Library/LinearAlgebra/P/F.lean"
    mod = "Library.LinearAlgebra.P.F"
    _mk_decl_file(tmp_path, rel, ["aa", "aa_2"])
    _classify_setup(monkeypatch)
    si = [(f"{mod}.aa", rel), (f"{mod}.aa_2", rel)]
    plan, skipped = dedup._classify_pairs(
        tmp_path, P, [(f"{mod}.aa_2", f"{mod}.aa")], scope_index=si)
    assert plan.get(f"{mod}.aa_2", (None, ""))[1] == "drop"
    assert skipped == []


def _mk_decl_file_imports(tmp_path, rel, names, imports):
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    body = "import Mathlib\n" + "".join(f"import {m}\n" for m in imports)
    body += "\n".join(f"theorem {n} : True := by trivial" for n in names) + "\n"
    p.write_text(body, encoding="utf-8")


def test_file_dep_closure_transitive(tmp_path) -> None:
    mod = "Library.LinearAlgebra.P"
    _mk_decl_file_imports(tmp_path, "Library/LinearAlgebra/P/Base.lean", ["b"], [])
    _mk_decl_file_imports(tmp_path, "Library/LinearAlgebra/P/Mid.lean", ["m"],
                          [f"{mod}.Base"])
    _mk_decl_file_imports(tmp_path, "Library/LinearAlgebra/P/Top.lean", ["t"],
                          [f"{mod}.Mid"])
    scope = [_vdecl("b", "b : True", module=f"{mod}.Base",
                    rel="Library/LinearAlgebra/P/Base.lean"),
             _vdecl("m", "m : True", module=f"{mod}.Mid",
                    rel="Library/LinearAlgebra/P/Mid.lean"),
             _vdecl("t", "t : True", module=f"{mod}.Top",
                    rel="Library/LinearAlgebra/P/Top.lean")]
    cl = dedup._file_dep_closure(tmp_path, scope)
    assert cl["Library/LinearAlgebra/P/Top.lean"] == frozenset(
        {"Library/LinearAlgebra/P/Mid.lean", "Library/LinearAlgebra/P/Base.lean"})
    assert cl["Library/LinearAlgebra/P/Base.lean"] == frozenset()


def test_classify_cross_file_skips_survivor_in_consumer(tmp_path, monkeypatch) -> None:
    # The GridConstruction→GridReindex bug: X (dropped, longer name) is in the
    # DEPENDENCY; the shorter-named survivor Y is in the CONSUMER (imports X's
    # file). `_survivor` agrees (Y shorter) but Y is downstream → unsafe rewire →
    # must SKIP, not drop.
    P = "LinearAlgebra.p"
    mod = "Library.LinearAlgebra.P"
    dep = "Library/LinearAlgebra/P/Dep.lean"
    cons = "Library/LinearAlgebra/P/Cons.lean"
    _mk_decl_file_imports(tmp_path, dep, ["aa_much_longer"], [])
    _mk_decl_file_imports(tmp_path, cons, ["aa"], [f"{mod}.Dep"])   # Cons imports Dep
    _classify_setup(monkeypatch)
    si = [(f"{mod}.Dep.aa_much_longer", dep), (f"{mod}.Cons.aa", cons)]
    plan, skipped = dedup._classify_pairs(
        tmp_path, P, [(f"{mod}.Dep.aa_much_longer", f"{mod}.Cons.aa")], scope_index=si)
    assert plan == {} and len(skipped) == 1                 # survivor downstream → skip


def test_classify_cross_file_drops_when_survivor_is_dependency(tmp_path, monkeypatch) -> None:
    # Safe cross-file: X (dropped, longer) is in the CONSUMER; the shorter
    # survivor Y is in the DEPENDENCY (X's file imports Y's) → every consumer of X
    # already sees Y → drop is safe.
    P = "LinearAlgebra.p"
    mod = "Library.LinearAlgebra.P"
    dep = "Library/LinearAlgebra/P/Dep.lean"
    cons = "Library/LinearAlgebra/P/Cons.lean"
    _mk_decl_file_imports(tmp_path, dep, ["aa"], [])
    _mk_decl_file_imports(tmp_path, cons, ["aa_much_longer"], [f"{mod}.Dep"])
    _classify_setup(monkeypatch)
    si = [(f"{mod}.Dep.aa", dep), (f"{mod}.Cons.aa_much_longer", cons)]
    plan, skipped = dedup._classify_pairs(
        tmp_path, P, [(f"{mod}.Cons.aa_much_longer", f"{mod}.Dep.aa")], scope_index=si)
    assert plan.get(f"{mod}.Cons.aa_much_longer", (None, ""))[1] == "drop"
    assert skipped == []


def test_resolve_drop_chains_follows_to_final_survivor() -> None:
    z = _decl("Library.LA.P.F.aa")        # final survivor (not dropped)
    y = _decl("Library.LA.P.F.bbb")       # dropped → z
    x = _decl("Library.LA.P.F.cccc")      # dropped → y
    by_fqn = {d.fqn: d for d in (x, y, z)}
    plan = {x.fqn: (y, "drop"), y.fqn: (z, "drop")}
    out = dedup._resolve_drop_chains(plan, by_fqn)
    assert out[x.fqn][0].fqn == z.fqn     # x repointed past dropped y → z
    assert out[y.fqn][0].fqn == z.fqn


def test_resolve_drop_chains_leaves_non_chained_and_bridge() -> None:
    surv = _decl("Library.LA.P.F.aa")     # survivor (not dropped)
    x = _decl("Library.LA.P.F.bbb")       # drop → surv (no chain)
    b = _decl("Library.LA.P.F.cccc")      # bridge → surv (untouched by resolver)
    by_fqn = {d.fqn: d for d in (surv, x, b)}
    plan = {x.fqn: (surv, "drop"), b.fqn: (surv, "bridge")}
    out = dedup._resolve_drop_chains(plan, by_fqn)
    assert out[x.fqn] == (surv, "drop")   # unchanged
    assert out[b.fqn] == (surv, "bridge")  # bridge entries never repointed


# ---------------------------------------------------------------------
# P3-(2) — variable extraction: binder parsing + #check (e)-gate loop
# ---------------------------------------------------------------------

def _vdecl(name, sig, module="Library.P.F", rel="Library/P/F.lean"):
    return dedup._Decl(fqn=f"{module}.{name}", rel=rel, module=module,
                       name=name, sig=sig, binders=0, concl_tokens=frozenset())


def test_bracket_groups_splits_top_level_only() -> None:
    assert dedup._bracket_groups("{K : Type*} [Field K] (U : Submodule K V)") == [
        "{K : Type*}", "[Field K]", "(U : Submodule K V)"]
    # inner [K] in a binder must not end the group
    assert dedup._bracket_groups("(f : V →ₗ[K] V)") == ["(f : V →ₗ[K] V)"]


def test_binder_atoms_prenex_and_explicit() -> None:
    assert dedup._binder_atoms("∀ {K : Type*} [Field K] (U : T), P") == [
        "{K : Type*}", "[Field K]", "(U : T)"]
    assert dedup._binder_atoms("(a : T) (b : S) : P") == ["(a : T)", "(b : S)"]
    # leading-colon prenex form (as _load_decls yields)
    assert dedup._binder_atoms(": ∀ {K : Type*} (U : T), v ∉ U → P") == [
        "{K : Type*}", "(U : T)"]


def test_is_prenex() -> None:
    assert dedup._is_prenex(": ∀ {K : Type*}, P") is True
    assert dedup._is_prenex("∀ {K}, P") is True
    assert dedup._is_prenex("(a : T) : P") is False


def test_shared_binders_intersection() -> None:
    d1 = _vdecl("foo", "∀ {K : Type*} [Field K] (U : T), P")
    d2 = _vdecl("bar", "∀ {K : Type*} [Field K] (V : S), Q")
    # shared (count 2) returned, decl-local (U/V, count 1) dropped; alpha order
    assert dedup._shared_binders([d1, d2]) == ["[Field K]", "{K : Type*}"]
    assert dedup._shared_binders([d1]) == []          # nothing shared on one decl


def test_norm_type_collapses_ws_and_universes() -> None:
    assert (cl_common._norm_type("∀ {K : Type u_1}  {V : Type u_2},\n  P")
            == "∀ {K : Type u} {V : Type u}, P")


def _setup_var(tmp_path, rel, content, *, prompt="variable_extract.md"):
    if prompt:
        pd = tmp_path / "Tooling" / "prompts" / "librarian"
        pd.mkdir(parents=True, exist_ok=True)
        (pd / prompt).write_text("x", encoding="utf-8")
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def _fake_typecheck(monkeypatch, results):
    seq = {"n": 0}

    def _tc(ws, text, fqns, **k):
        i = seq["n"]
        seq["n"] += 1
        return results[i]
    monkeypatch.setattr(cl_common, "_typecheck_capturing_types", _tc)
    return seq


def _json_info(data):
    import json
    return json.dumps({"severity": "information", "data": data})


def test_parse_check_output_at_prefixed() -> None:
    out = _json_info("@L.A.foo : ∀ {n : ℕ}, n = n")
    types, errs = cl_common._parse_check_output(out, ["L.A.foo"])
    assert errs == [] and types == {"L.A.foo": "∀ {n : ℕ}, n = n"}


def test_parse_check_output_no_at_when_no_implicit() -> None:
    # Lean drops the `@` for a decl with only explicit binders (the bug that
    # skipped whole files: parser matched only `@foo :`).
    out = _json_info("L.A.foo : ∀ (S : T), P S")
    types, _ = cl_common._parse_check_output(out, ["L.A.foo"])
    assert types == {"L.A.foo": "∀ (S : T), P S"}


def test_parse_check_output_universe_annotation() -> None:
    out = _json_info("@L.A.foo.{u_1} : Type u_1 → Type u_1")
    types, _ = cl_common._parse_check_output(out, ["L.A.foo"])
    assert types == {"L.A.foo": "Type u → Type u"}        # u_1 normalized


def test_parse_check_output_no_prefix_collision() -> None:
    out = "\n".join([_json_info("@L.A.foo_bar : Bar"), _json_info("@L.A.foo : Foo")])
    types, _ = cl_common._parse_check_output(out, ["L.A.foo", "L.A.foo_bar"])
    assert types == {"L.A.foo": "Foo", "L.A.foo_bar": "Bar"}


def test_parse_check_output_collects_errors() -> None:
    import json
    out = json.dumps({"severity": "error", "data": "unknown identifier 'baz'"})
    types, errs = cl_common._parse_check_output(out, ["L.A.foo"])
    assert types == {} and errs == ["unknown identifier 'baz'"]


# ---------------------------------------------------------------------
# A — unused-arg removal (mechanical): parse linter + strip instance binders
# ---------------------------------------------------------------------

_LINT_OUT = """\
warning: Library/X.lean:14:0: `directsum_prod_uncurry` does not use the following hypotheses in its type:
  • [DecidableEq α] (#5)
  • [DecidableEq β] (#6)

Consider removing these hypotheses and using `classical` in the proof instead.
warning: Library/X.lean:30:0: `other_lemma` does not use the following hypotheses in its type:
  • (h : P) (#3)
"""


def test_parse_unused_hyps() -> None:
    assert cl_mechanical._parse_unused_hyps(_LINT_OUT) == {
        "directsum_prod_uncurry": ["[DecidableEq α]", "[DecidableEq β]"],
        "other_lemma": ["(h : P)"]}


def test_strip_instance_binders_removes_only_instances() -> None:
    text = ("theorem foo {α : Type} [DecidableEq α] [Fintype α] (h : P α) : Q :="
            " by exact h\n")
    out, changed = cl_mechanical._strip_instance_binders(text, "foo", ["[DecidableEq α]"])
    assert changed
    assert "[DecidableEq α]" not in out
    assert "{α : Type}" in out and "[Fintype α]" in out and "(h : P α)" in out


def test_strip_instance_binders_skips_explicit() -> None:
    text = "theorem foo (h : P) : Q := by exact h\n"
    out, changed = cl_mechanical._strip_instance_binders(text, "foo", ["(h : P)"])
    assert not changed and out == text          # explicit binders are not v1 scope


def test_insert_classical_after_by() -> None:
    out = cl_mechanical._insert_classical("theorem foo {α} : Q := by\n  exact rfl\n", "foo")
    assert ":= by\n  classical\n  exact rfl" in out


def test_insert_classical_skips_term_mode() -> None:
    text = "theorem foo {α} : Q := rfl\n"
    assert cl_mechanical._insert_classical(text, "foo") == text   # term-mode untouched


def test_strip_framework_comments(tmp_path, monkeypatch) -> None:
    rel = "Library/P/F.lean"
    (tmp_path / "Library" / "P").mkdir(parents=True)
    src = (
        "import Mathlib\n\n"
        "/-- Real docstring, keep me. -/\n"
        "-- entry_kind: Builder\n"
        "-- Direct construction (was: circular `pad_and_place`).\n"
        "--   `sorted_enum` (sub-goal): enumerate in order.\n"
        "theorem foo : True := by trivial\n\n"
        "-- a legit clarifying note (no framework jargon)\n"
        "theorem bar : True := by trivial\n")
    (tmp_path / rel).write_text(src, encoding="utf-8")
    monkeypatch.setattr(cl_common, "_missing_oleans", lambda ws, mods: [])
    monkeypatch.setattr(cl_common, "_lake_check", lambda ws, content, **k: (True, ""))
    assert dedup.file_cleanup_strip_framework_comments(tmp_path, "p", rel) is True
    out = (tmp_path / rel).read_text(encoding="utf-8")
    assert "entry_kind" not in out and "(was:" not in out and "sub-goal" not in out
    assert "/-- Real docstring, keep me. -/" in out          # docstring kept
    assert "-- a legit clarifying note" in out               # non-framework kept
    assert "theorem foo" in out and "theorem bar" in out      # decls intact


def test_strip_framework_comments_noop_when_clean(tmp_path, monkeypatch) -> None:
    rel = "Library/P/G.lean"
    (tmp_path / "Library" / "P").mkdir(parents=True)
    (tmp_path / rel).write_text(
        "import Mathlib\n\n/-- doc -/\ntheorem foo : True := by trivial\n",
        encoding="utf-8")
    monkeypatch.setattr(cl_common, "_lake_check", lambda ws, content, **k: (True, ""))
    assert dedup.file_cleanup_strip_framework_comments(tmp_path, "p", rel) is False


# ---------------------------------------------------------------------
# point 4 — cite-mathlib drop: detect pure alias + mechanical inline
# ---------------------------------------------------------------------

def test_pure_mathlib_citation() -> None:
    assert (dedup._pure_mathlib_citation("Ideal.iInf_span_singleton hg")
            == "Ideal.iInf_span_singleton hg")
    assert (dedup._pure_mathlib_citation("by exact Ideal.iInf_span_singleton hg")
            == "Ideal.iInf_span_singleton hg")             # `by exact` stripped
    assert dedup._pure_mathlib_citation("by simp") is None  # no dotted head
    assert dedup._pure_mathlib_citation("Library.P.foo x") is None   # Library alias
    assert dedup._pure_mathlib_citation("fun x => Foo.bar x") is None  # not a citation


def test_explicit_param_names() -> None:
    sig = "(g : ι → K) (hg : ∀ i, P i) {α : Type} [Inst α] : Concl"
    assert dedup._explicit_param_names(sig) == ["g", "hg"]


def test_inline_wrapper_call_substitutes_and_skips_header() -> None:
    text = ("theorem wrap (g : X) (hg : Y) : T := Ideal.iInf_span_singleton hg\n"
            "theorem use : T := wrap a b\n")
    out, n = dedup._inline_wrapper_call(
        text, "wrap", ["g", "hg"], "Ideal.iInf_span_singleton hg")
    assert n == 1                                           # only the call site
    assert ":= (Ideal.iInf_span_singleton b)\n" in out     # hg→b substituted
    assert "theorem wrap (g : X)" in out                   # header untouched


def test_inline_wrapper_call_skips_partial_application() -> None:
    text = "theorem use : T → T := wrap a\n"               # only 1 of 2 args
    out, n = dedup._inline_wrapper_call(text, "wrap", ["g", "hg"], "M.l hg")
    assert n == 0 and out == text


# ---------------------------------------------------------------------
# batch_defeq — INFRA (timeout / broken env) is logged, not a silent verdict
# ---------------------------------------------------------------------

def test_batch_defeq_infra_logs_and_keeps(tmp_path, monkeypatch, capsys) -> None:
    # A probe timeout (or broken env) must NOT be conflated with "not defeq":
    # return all-False (safe keep) but LOUDLY, so a load-dependent miss is
    # auditable (Fable-5 review; the old timeout path was a silent [False]*n).
    monkeypatch.setattr(dedup, "_missing_oleans", lambda ws, mods: [])
    monkeypatch.setattr(
        dedup._lp, "run_lean_source",
        lambda ws, content, **k: dedup._lp.LeanRun(None, "timeout after 240s", True))
    pairs = [(": True", "Mathlib", "trivial"), (": True", "Mathlib", "trivial")]
    out = dedup.batch_defeq(tmp_path, "p", pairs)
    assert out == [False, False]                  # infra → keep, not a verdict
    assert "INFRA" in capsys.readouterr().out     # audit trail


def test_batch_defeq_clean_build_all_defeq(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(dedup, "_missing_oleans", lambda ws, mods: [])
    monkeypatch.setattr(
        dedup._lp, "run_lean_source",
        lambda ws, content, **k: dedup._lp.LeanRun(0, "", False))   # clean
    pairs = [(": True", "Mathlib", "trivial"), (": True", "Mathlib", "trivial")]
    assert dedup.batch_defeq(tmp_path, "p", pairs) == [True, True]


# ---------------------------------------------------------------------
# deferred-rewire — same-module rename keeps bare refs bare (else cite-drop's
# bare-name matcher misses an over-qualified ref → dangling drop)
# ---------------------------------------------------------------------

def test_cleanup_one_file_same_module_rename_keeps_bare(tmp_path) -> None:
    rel = "Library/P/U.lean"
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("import Library.P.M\nopen Library.P.M\n"
                 "theorem a : T := by exact foo x\n"
                 "theorem b : T := by exact Library.P.M.foo x\n",
                 encoding="utf-8")
    X = _vdecl("foo", ": T", module="Library.P.M", rel="Library/P/M.lean")
    Y = _vdecl("bar", ": T", module="Library.P.M", rel="Library/P/M.lean")
    dedup._cleanup_one_file(tmp_path, rel, [], {}, {}, [(X, Y)],
                            dedup._Splicer(tmp_path))
    out = p.read_text(encoding="utf-8")
    assert "exact bar x" in out                       # bare ref stays bare
    assert "exact Library.P.M.bar x" in out           # qualified ref → new fqn
    assert "foo" not in out


def test_cleanup_one_file_cross_module_drop_qualifies(tmp_path) -> None:
    rel = "Library/P/U.lean"
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("import Library.P.M\nopen Library.P.M\n"
                 "theorem a : T := by exact foo x\n", encoding="utf-8")
    X = _vdecl("foo", ": T", module="Library.P.M", rel="Library/P/M.lean")
    Y = _vdecl("surv", ": T", module="Library.P.N", rel="Library/P/N.lean")
    dedup._cleanup_one_file(tmp_path, rel, [], {}, {}, [(X, Y)],
                            dedup._Splicer(tmp_path))
    out = p.read_text(encoding="utf-8")
    assert "exact Library.P.N.surv x" in out          # cross-module → fully qualified
    assert "import Library.P.N" in out                # survivor's module imported


# ---------------------------------------------------------------------
# P4 — decide (naming alignment + precise imports): parse / validate / apply
# ---------------------------------------------------------------------

def test_parse_decide_canonical_and_legacy_shapes() -> None:
    # canonical {"renames":…, "imports":…}
    r, i = cl_decide._parse_decide(
        '{"renames":{"a":"x"},"imports":["Mathlib.A.B"," Mathlib.C ",3]}')
    assert r == {"a": "x"} and i == ["Mathlib.A.B", "Mathlib.C"]
    # either key alone
    assert cl_decide._parse_decide('{"imports":["Mathlib.A"]}') == ({}, ["Mathlib.A"])
    assert cl_decide._parse_decide('{"renames":[{"old":"a","new":"x"}]}') == (
        {"a": "x"}, [])
    # legacy bare str→str object = renames-only
    assert cl_decide._parse_decide('{"a":"x","b":"y"}') == ({"a": "x", "b": "y"}, [])
    assert cl_decide._parse_decide("```json\n{\"a\":\"x\"}\n```") == ({"a": "x"}, [])
    assert cl_decide._parse_decide("not json") == ({}, [])
    assert cl_decide._parse_decide('{"a": 3}') == ({}, [])       # non-str value
    assert cl_decide._parse_decide('{"renames":{}, "imports":"x"}') == ({}, [])


def _mathlib_tree(tmp_path, *modules):
    """Vendored-mathlib stub: create `<ws>/.lake/packages/mathlib/<mod path>.lean`."""
    root = tmp_path / ".lake" / "packages" / "mathlib"
    for m in modules:
        p = root / (m.replace(".", "/") + ".lean")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("-- stub\n", encoding="utf-8")


def test_valid_imports_existence_and_shape(tmp_path) -> None:
    _mathlib_tree(tmp_path, "Mathlib.LinearAlgebra.Matrix.Block",
                  "Mathlib.RingTheory.PolynomialAlgebra")
    proposed = [
        "Mathlib.RingTheory.PolynomialAlgebra",   # exists → kept
        "Mathlib.LinearAlgebra.Matrix.Block",     # exists → kept (sorted first)
        "Mathlib.LinearAlgebra.Matrix.Block",     # dup → once
        "Mathlib.Totally.Hallucinated",           # no such file → dropped
        "Mathlib",                                # bare umbrella → dropped
        "Library.P.F",                            # not Mathlib.* → dropped
        "Mathlib.Bad-Seg",                        # invalid segment → dropped
    ]
    assert cl_decide._valid_imports(proposed, tmp_path) == [
        "Mathlib.LinearAlgebra.Matrix.Block",
        "Mathlib.RingTheory.PolynomialAlgebra"]


def test_swap_umbrella_import() -> None:
    text = ("import Library.P.Sib\nimport Mathlib\n\nopen Foo\n\n"
            "theorem t : P := by trivial\n")
    out, changed = cl_decide._swap_umbrella_import(
        text, ["Mathlib.A.B", "Mathlib.C"])
    assert changed
    assert ("import Library.P.Sib\nimport Mathlib.A.B\nimport Mathlib.C\n\n"
            "open Foo") in out
    # umbrella absent / body mention only → no-op (body never touched)
    body = "import Mathlib.A.B\n\n-- import Mathlib\ntheorem t : P := trivial\n"
    assert cl_decide._swap_umbrella_import(body, ["Mathlib.C"]) == (body, False)
    assert cl_decide._swap_umbrella_import(text, []) == (text, False)


def test_valid_renames_filters() -> None:
    own = {"lemma_3", "step_aux", "good_name"}
    existing = {"add_comm", "step_aux"}    # step_aux also defined elsewhere
    proposed = {
        "lemma_3": "det_smul",        # ok
        "step_aux": "add_comm",       # new collides with existing → drop
        "missing": "foo",            # old not in own → drop
        "good_name": "good_name",     # new == old → drop
        "x": "bad-name",             # invalid ident → drop (and old not own)
    }
    assert cl_common._valid_renames(proposed, own_leaves=own,
                                existing_leaves=existing) == {"lemma_3": "det_smul"}


def test_valid_renames_no_chain_or_dup_target() -> None:
    own = {"a", "b", "c"}
    # a→b would chain (b is itself an old); two olds → same new is a dup target
    proposed = {"a": "b", "b": "z", "c": "z"}
    out = cl_common._valid_renames(proposed, own_leaves=own, existing_leaves=set())
    assert "a" not in out                       # new 'b' is an old → dropped
    assert out == {"b": "z"}                    # 'c':'z' dropped as dup target


def _setup_decide(tmp_path, rel, content):
    pd = tmp_path / "Tooling" / "prompts" / "librarian"
    pd.mkdir(parents=True, exist_ok=True)
    (pd / "decide.md").write_text("x", encoding="utf-8")
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def _fake_decide_spawn(monkeypatch, outputs):
    """Patch agent.spawn_llm to write outputs[i] (str|None) as decide.json."""
    from Tooling import agent
    calls = {"n": 0}

    def _spawn(*, kind, prompt_path, problem_dir, attempts_dir, session_id):
        i = calls["n"]
        calls["n"] += 1
        o = outputs[i] if i < len(outputs) else None
        if o is not None:
            (attempts_dir / "decide.json").write_text(o, encoding="utf-8")
        return 0
    monkeypatch.setattr(agent, "spawn_llm", _spawn)
    return calls


def _fake_filecopy(monkeypatch, results):
    seq = {"n": 0}

    def _bc(ws, text, **k):
        i = seq["n"]
        seq["n"] += 1
        return results[i]
    monkeypatch.setattr(cl_common, "_build_file_copy_isolated", _bc)
    return seq


def test_file_cleanup_decide_noop_without_prompt(tmp_path) -> None:
    rel = "Library/P/F.lean"
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("import Mathlib\n", encoding="utf-8")     # no prompt file
    d = _vdecl("lemma_3", "(a : T) : P")
    assert dedup.file_cleanup_decide(tmp_path, "p", rel, [d],
                                     scope=[d], pool=[]) == ({}, False)


def test_file_cleanup_decide_renames_header_refs_and_imports(tmp_path,
                                                             monkeypatch) -> None:
    rel = "Library/P/F.lean"
    module = "Library.P.F"
    content = ("import Library.P.Sib\nimport Mathlib\n"
               "theorem lemma_3 (a : T) : P := by trivial\n"
               "theorem uses_it : P := lemma_3 x\n")   # in-file reference
    _setup_decide(tmp_path, rel, content)
    _mathlib_tree(tmp_path, "Mathlib.A.B")
    d3 = _vdecl("lemma_3", "(a : T) : P", module=module, rel=rel)
    du = _vdecl("uses_it", ": P", module=module, rel=rel)
    _fake_decide_spawn(monkeypatch, [
        '{"renames":{"lemma_3":"trivial_P"},"imports":["Mathlib.A.B"]}'])
    _fake_filecopy(monkeypatch, [(True, "")])
    out = dedup.file_cleanup_decide(tmp_path, "p", rel, [d3, du],
                                    scope=[d3, du], pool=[])
    assert out == ({f"{module}.lemma_3": f"{module}.trivial_P"}, True)
    txt = (tmp_path / rel).read_text(encoding="utf-8")
    assert "theorem trivial_P (a : T)" in txt
    assert "lemma_3" not in txt                  # header + ref both renamed
    assert "trivial_P x" in txt                  # the in-file reference rewired
    assert "import Mathlib.A.B" in txt           # umbrella swapped
    assert "import Mathlib\n" not in txt
    assert "import Library.P.Sib" in txt         # sibling import untouched


def test_file_cleanup_decide_reverts_on_build_failure(tmp_path, monkeypatch) -> None:
    rel = "Library/P/F.lean"
    module = "Library.P.F"
    content = "import Mathlib\ntheorem lemma_3 (a : T) : P := by trivial\n"
    _setup_decide(tmp_path, rel, content)
    d = _vdecl("lemma_3", "(a : T) : P", module=module, rel=rel)
    # 1 try + 1 retry, both rename-only proposals fail to build → keep original
    _fake_decide_spawn(monkeypatch, ['{"renames":{"lemma_3":"foo"}}',
                                     '{"renames":{"lemma_3":"bar"}}'])
    _fake_filecopy(monkeypatch, [(False, "collision"), (False, "collision")])
    assert dedup.file_cleanup_decide(tmp_path, "p", rel, [d],
                                     scope=[d], pool=[]) == ({}, False)
    assert (tmp_path / rel).read_text(encoding="utf-8") == content   # unchanged


def test_file_cleanup_decide_falls_back_to_renames_only(tmp_path,
                                                        monkeypatch) -> None:
    # Degrade ladder: renames+imports red on both tries → rung 3 gates the
    # renames-only text (umbrella kept) → green → a bad import set never
    # costs a rename.
    rel = "Library/P/F.lean"
    module = "Library.P.F"
    content = "import Mathlib\ntheorem lemma_3 (a : T) : P := by trivial\n"
    _setup_decide(tmp_path, rel, content)
    _mathlib_tree(tmp_path, "Mathlib.Too.Narrow")
    d = _vdecl("lemma_3", "(a : T) : P", module=module, rel=rel)
    prop = '{"renames":{"lemma_3":"trivial_P"},"imports":["Mathlib.Too.Narrow"]}'
    _fake_decide_spawn(monkeypatch, [prop, prop])
    _fake_filecopy(monkeypatch, [(False, "unknown identifier"),
                                 (False, "unknown identifier"),
                                 (True, "")])         # rung 3: renames-only green
    out = dedup.file_cleanup_decide(tmp_path, "p", rel, [d],
                                    scope=[d], pool=[])
    assert out == ({f"{module}.lemma_3": f"{module}.trivial_P"}, False)
    txt = (tmp_path / rel).read_text(encoding="utf-8")
    assert "theorem trivial_P" in txt
    assert "import Mathlib\n" in txt             # umbrella kept
    assert "Mathlib.Too.Narrow" not in txt


def test_file_cleanup_decide_imports_only_proposal(tmp_path, monkeypatch) -> None:
    rel = "Library/P/F.lean"
    content = "import Mathlib\ntheorem add_comm (a : T) : P := by trivial\n"
    _setup_decide(tmp_path, rel, content)
    _mathlib_tree(tmp_path, "Mathlib.A.B")
    d = _vdecl("add_comm", "(a : T) : P", rel=rel)
    _fake_decide_spawn(monkeypatch, ['{"renames":{},"imports":["Mathlib.A.B"]}'])
    _fake_filecopy(monkeypatch, [(True, "")])
    out = dedup.file_cleanup_decide(tmp_path, "p", rel, [d],
                                    scope=[d], pool=[])
    assert out == ({}, True)
    txt = (tmp_path / rel).read_text(encoding="utf-8")
    assert "import Mathlib.A.B" in txt and "import Mathlib\n" not in txt


def test_file_cleanup_decide_renames_keystone_main(tmp_path, monkeypatch) -> None:
    # `main` is the framework keystone placeholder — it renames like any other
    # decl (Gate B / INDEX cite it by DB target_name, updated on rename).
    rel = "Library/P/F.lean"
    module = "Library.P.F"
    content = "import Mathlib\ntheorem main (a : T) : P := by trivial\n"
    _setup_decide(tmp_path, rel, content)
    d = _vdecl("main", "(a : T) : P", module=module, rel=rel)
    _fake_decide_spawn(monkeypatch, ['{"renames":{"main":"svd_decomposition"}}'])
    _fake_filecopy(monkeypatch, [(True, "")])
    out = dedup.file_cleanup_decide(tmp_path, "p", rel, [d],
                                    scope=[d], pool=[])
    assert out == ({f"{module}.main": f"{module}.svd_decomposition"}, False)
    assert "theorem svd_decomposition (a : T)" in (
        tmp_path / rel).read_text(encoding="utf-8")


def test_file_cleanup_decide_noop_when_nothing_to_decide(tmp_path,
                                                         monkeypatch) -> None:
    rel = "Library/P/F.lean"
    _setup_decide(tmp_path, rel,
                  "import Mathlib\ntheorem add_comm (a : T) : P := by trivial\n")
    d = _vdecl("add_comm", "(a : T) : P", rel=rel)
    spy = _fake_decide_spawn(monkeypatch, ['{"renames":{},"imports":[]}'])
    bc = _fake_filecopy(monkeypatch, [])
    assert dedup.file_cleanup_decide(tmp_path, "p", rel, [d],
                                     scope=[d], pool=[]) == ({}, False)
    assert spy["n"] == 1 and bc["n"] == 0             # spawned once, never built


# ---------------------------------------------------------------------
# (e) polish — merged variable+docstring+style+warning pass (type-preserving)
# ---------------------------------------------------------------------

def _fake_polish_spawn(monkeypatch, outputs):
    """Patch agent.spawn_llm to write outputs[i] (str|None) as polished.lean."""
    from Tooling import agent
    calls = {"n": 0}

    def _spawn(*, kind, prompt_path, problem_dir, attempts_dir, session_id):
        i = calls["n"]
        calls["n"] += 1
        o = outputs[i] if i < len(outputs) else None
        if o is not None:
            (attempts_dir / "polished.lean").write_text(o, encoding="utf-8")
        return 0
    monkeypatch.setattr(agent, "spawn_llm", _spawn)
    return calls


def _fake_bwo_seq(monkeypatch, outputs):
    """Patch _build_with_output to return (True, outputs[i]) — the warning view."""
    seq = {"n": 0}

    def _bwo(ws, content, *, prefix, timeout=240):
        i = seq["n"]
        seq["n"] += 1
        return True, (outputs[i] if i < len(outputs) else "")
    monkeypatch.setattr(cl_common, "_build_with_output", _bwo)
    return seq


def test_polish_warnings_filters() -> None:
    out = ("warning: F.lean:10:3: unused variable `h`\n"
           "warning: F.lean:12:0: This line exceeds the 100 character limit, "
           "please shorten it!\n"
           "warning: F.lean:5:0: `A.A.foo` namespace is duplicated\n")  # not polish's
    w = cl_polish._polish_warnings(out)
    assert len(w) == 2 and not any("duplicated" in x for x in w)


def test_file_cleanup_polish_noop_without_prompt(tmp_path) -> None:
    rel = "Library/P/F.lean"
    _setup_var(tmp_path, rel, "import Mathlib\n", prompt=None)   # no prompt file
    assert dedup.file_cleanup_polish(tmp_path, "p", rel,
                                     [_vdecl("foo", "(a : T) : P")]) is False


def test_file_cleanup_polish_success_no_warnings(tmp_path, monkeypatch) -> None:
    rel = "Library/P/F.lean"
    _setup_var(tmp_path, rel, "import Mathlib\n-- orig\n", prompt="polish.md")
    d = _vdecl("foo", "(a : T) : P")
    new = "import Mathlib\n/-- doc -/\ntheorem foo (a : T) : P := by trivial\n"
    _fake_polish_spawn(monkeypatch, [new])
    _fake_typecheck(monkeypatch, [(True, "", {d.fqn: "T"}),    # base snapshot
                                  (True, "", {d.fqn: "T"})])   # attempt: same type
    _fake_bwo_seq(monkeypatch, [""])                           # no warnings → done
    assert dedup.file_cleanup_polish(tmp_path, "p", rel, [d]) is True
    assert (tmp_path / rel).read_text(encoding="utf-8") == new


def test_file_cleanup_polish_reverts_on_type_change(tmp_path, monkeypatch) -> None:
    rel = "Library/P/F.lean"
    original = "import Mathlib\n-- orig\n"
    _setup_var(tmp_path, rel, original, prompt="polish.md")
    d = _vdecl("foo", "(a : T) : P")
    _fake_polish_spawn(monkeypatch, ["v1\n", "v2\n", "v3\n"])      # 1 + 2 retries
    _fake_typecheck(monkeypatch, [(True, "", {d.fqn: "T"})]        # base
                    + [(True, "", {d.fqn: "CHANGED"})] * 3)        # type drifts each try
    _fake_bwo_seq(monkeypatch, [])                                 # never reached
    assert dedup.file_cleanup_polish(tmp_path, "p", rel, [d]) is False
    assert (tmp_path / rel).read_text(encoding="utf-8") == original   # kept


def test_file_cleanup_polish_retries_warnings_keeps_best(tmp_path,
                                                         monkeypatch) -> None:
    rel = "Library/P/F.lean"
    _setup_var(tmp_path, rel, "import Mathlib\n-- orig\n", prompt="polish.md")
    d = _vdecl("foo", "(a : T) : P")
    v1, v2 = "import Mathlib\n-- v1\n", "import Mathlib\n-- v2 clean\n"
    _fake_polish_spawn(monkeypatch, [v1, v2])
    _fake_typecheck(monkeypatch, [(True, "", {d.fqn: "T"}),    # base
                                  (True, "", {d.fqn: "T"}),    # v1 type ok
                                  (True, "", {d.fqn: "T"})])   # v2 type ok
    _fake_bwo_seq(monkeypatch, ["warning: x:1:0: unused variable `h`\n", ""])
    assert dedup.file_cleanup_polish(tmp_path, "p", rel, [d]) is True
    assert (tmp_path / rel).read_text(encoding="utf-8") == v2   # kept the clean retry


# ---------------------------------------------------------------------
# bridge cite-drop — residual-reference veto (primary e2e 2026-06-10)
# ---------------------------------------------------------------------

def _cite_drop_ws(tmp_path, wrapper_sig_args, consumer_call):
    """Two-file workspace: F.lean holds a pure-mathlib wrapper `w`, G.lean a
    consumer calling it. Returns the scope decls."""
    f = tmp_path / "Library/P/F.lean"
    g = tmp_path / "Library/P/G.lean"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(
        "import Mathlib\n"
        f"theorem w {wrapper_sig_args} :\n"
        "    0 < n :=\n"
        "  Nat.pos_of_ne_zero h\n"
        "theorem keep : True := trivial\n", encoding="utf-8")
    g.write_text(
        "import Mathlib\n"
        f"theorem uses : True := by have := {consumer_call}; trivial\n",
        encoding="utf-8")
    sig = f"{wrapper_sig_args} : 0 < n"
    return [dedup._Decl(fqn="Library.P.F.w", rel="Library/P/F.lean",
                        module="Library.P.F", name="w", sig=sig,
                        binders=0, concl_tokens=frozenset()),
            dedup._Decl(fqn="Library.P.G.uses", rel="Library/P/G.lean",
                        module="Library.P.G", name="uses", sig=": True",
                        binders=0, concl_tokens=frozenset())]


def _patch_cite_drop_env(monkeypatch, build_results=None):
    from Tooling.pipeline import _lake
    monkeypatch.setattr(_lake, "lake_build_modules", lambda ws, mods: (True, ""))
    monkeypatch.setattr(dedup, "_missing_oleans", lambda ws, mods: [])
    monkeypatch.setattr(dedup, "_build_file_copy_isolated",
                        lambda ws, t, **k: (True, ""))


def test_cite_drop_vetoes_on_partial_application_reference(tmp_path,
                                                           monkeypatch) -> None:
    # polish un-∀'d the wrapper → 2 explicit params, but the consumer calls it
    # with 1 arg (partial application). The inliner skips partials by design —
    # the drop must then be VETOED (a dangling reference in an untouched
    # consumer broke the whole problem at the bridge build, primary e2e).
    scope = _cite_drop_ws(tmp_path, "(n : Nat) (h : n ≠ 0)", "w 3")
    _patch_cite_drop_env(monkeypatch)
    out = dedup.cite_drop_aliases(tmp_path, "p", scope)
    assert out == {}                                          # nothing dropped
    txt = (tmp_path / "Library/P/F.lean").read_text(encoding="utf-8")
    assert "theorem w " in txt                                # wrapper kept


def test_cite_drop_inlines_and_drops_full_application(tmp_path,
                                                      monkeypatch) -> None:
    scope = _cite_drop_ws(tmp_path, "(n : Nat) (h : n ≠ 0)", "w 3 hx")
    _patch_cite_drop_env(monkeypatch)
    out = dedup.cite_drop_aliases(tmp_path, "p", scope)
    assert out == {"Library.P.F.w": "Nat.pos_of_ne_zero"}
    assert "theorem w " not in (tmp_path / "Library/P/F.lean").read_text(
        encoding="utf-8")                                     # dropped
    g = (tmp_path / "Library/P/G.lean").read_text(encoding="utf-8")
    assert "(Nat.pos_of_ne_zero hx)" in g                     # inlined
    assert "w 3 hx" not in g


# ---------------------------------------------------------------------
# audit — final free-form review (fences + declared-rename gate)
# ---------------------------------------------------------------------

def _setup_audit(tmp_path, rel, content):
    pd = tmp_path / "Tooling" / "prompts" / "librarian"
    pd.mkdir(parents=True, exist_ok=True)
    (pd / "audit.md").write_text("x", encoding="utf-8")
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def _fake_audit_spawn(monkeypatch, outputs):
    """outputs[i] = (audited_text|None, renames_json|None)."""
    from Tooling import agent
    calls = {"n": 0}

    def _spawn(*, kind, prompt_path, problem_dir, attempts_dir, session_id):
        i = calls["n"]
        calls["n"] += 1
        text, ren = outputs[i] if i < len(outputs) else (None, None)
        if text is not None:
            (attempts_dir / "audited.lean").write_text(text, encoding="utf-8")
        if ren is not None:
            (attempts_dir / "renames.json").write_text(ren, encoding="utf-8")
        return 0
    monkeypatch.setattr(agent, "spawn_llm", _spawn)
    return calls


def _fake_audit_types(monkeypatch, type_of):
    """Stub typecheck: every requested fqn gets type_of(fqn)."""
    monkeypatch.setattr(
        cl_common, "_typecheck_capturing_types",
        lambda ws, text, fqns, **k: (True, "", {f: type_of(f) for f in fqns}))
    monkeypatch.setattr(cl_common, "_build_with_output",
                        lambda ws, text, **k: (True, ""))


_AUDIT_SRC = ("import Mathlib.A.B\n\nnamespace Library.P.F\n\n"
              "theorem foo_bar : P := trivial\n\nend Library.P.F\n")


def test_audit_free_rewrite_accepted(tmp_path, monkeypatch) -> None:
    rel = "Library/P/F.lean"
    _setup_audit(tmp_path, rel, _AUDIT_SRC)
    rewritten = _AUDIT_SRC.replace("theorem foo_bar",
                                   "/-- doc -/\ntheorem foo_bar")
    _fake_audit_spawn(monkeypatch, [(rewritten, None)])
    _fake_audit_types(monkeypatch, lambda f: "T")
    d = _vdecl("foo_bar", ": P", module="Library.P.F", rel=rel)
    out = dedup.file_cleanup_audit(tmp_path, "p", rel, [d], scope=[d], pool=[])
    assert out == ({}, True)
    assert "/-- doc -/" in (tmp_path / rel).read_text(encoding="utf-8")


def test_audit_declared_rename_flows(tmp_path, monkeypatch) -> None:
    rel = "Library/P/F.lean"
    _setup_audit(tmp_path, rel, _AUDIT_SRC)
    rewritten = _AUDIT_SRC.replace("foo_bar", "bar_of_foo")
    _fake_audit_spawn(monkeypatch, [(rewritten, '{"foo_bar":"bar_of_foo"}')])
    # type mentions the decl's own leaf — must be compared modulo the rename
    _fake_audit_types(monkeypatch,
                      lambda f: f"T {f.rsplit('.', 1)[-1]}")
    d = _vdecl("foo_bar", ": P", module="Library.P.F", rel=rel)
    out = dedup.file_cleanup_audit(tmp_path, "p", rel, [d], scope=[d], pool=[])
    assert out == ({"Library.P.F.foo_bar": "Library.P.F.bar_of_foo"}, True)
    assert "bar_of_foo" in (tmp_path / rel).read_text(encoding="utf-8")


def test_audit_import_and_namespace_fences(tmp_path, monkeypatch) -> None:
    rel = "Library/P/F.lean"
    _setup_audit(tmp_path, rel, _AUDIT_SRC)
    bad_import = _AUDIT_SRC.replace("import Mathlib.A.B", "import Mathlib")
    bad_ns = _AUDIT_SRC.replace("namespace Library.P.F", "namespace Module.End")
    _fake_audit_spawn(monkeypatch, [(bad_import, None), (bad_ns, None),
                                    (None, None)])
    _fake_audit_types(monkeypatch, lambda f: "T")
    d = _vdecl("foo_bar", ": P", module="Library.P.F", rel=rel)
    out = dedup.file_cleanup_audit(tmp_path, "p", rel, [d], scope=[d], pool=[])
    assert out == ({}, False)                                 # both rejected
    assert (tmp_path / rel).read_text(encoding="utf-8") == _AUDIT_SRC


def test_audit_type_change_reverts(tmp_path, monkeypatch) -> None:
    rel = "Library/P/F.lean"
    _setup_audit(tmp_path, rel, _AUDIT_SRC)
    rewritten = _AUDIT_SRC.replace(": P :=", ": Q :=")
    _fake_audit_spawn(monkeypatch, [(rewritten, None)] * 3)
    calls = {"n": 0}

    def _types(ws, text, fqns, **k):
        calls["n"] += 1
        t = "P" if calls["n"] == 1 else "Q"       # snapshot then drifted
        return True, "", {f: t for f in fqns}
    monkeypatch.setattr(cl_common, "_typecheck_capturing_types", _types)
    monkeypatch.setattr(cl_common, "_build_with_output",
                        lambda ws, text, **k: (True, ""))
    d = _vdecl("foo_bar", ": P", module="Library.P.F", rel=rel)
    out = dedup.file_cleanup_audit(tmp_path, "p", rel, [d], scope=[d], pool=[])
    assert out == ({}, False)
    assert (tmp_path / rel).read_text(encoding="utf-8") == _AUDIT_SRC


def test_audit_noop_when_unchanged(tmp_path, monkeypatch) -> None:
    rel = "Library/P/F.lean"
    _setup_audit(tmp_path, rel, _AUDIT_SRC)
    _fake_audit_spawn(monkeypatch, [(_AUDIT_SRC, None)])
    _fake_audit_types(monkeypatch, lambda f: "T")
    d = _vdecl("foo_bar", ": P", module="Library.P.F", rel=rel)
    assert dedup.file_cleanup_audit(tmp_path, "p", rel, [d],
                                    scope=[d], pool=[]) == ({}, False)


def test_staged_file_agentic_stages_gate_bridged_decls(tmp_path,
                                                       monkeypatch) -> None:
    # A bridged alias stays IN the file → polish/decide/audit must receive it in
    # their gate set. Gating only `survivor_decls` let audit delete the alias
    # green (rcf e2e 2026-06-10: bridged `block_companion` vanished → consumer
    # dangling → bridge red).
    rel = "Library/P/F.lean"
    a = _vdecl("keep_me", ": P", module="Library.P.F", rel=rel)
    b = _vdecl("bridge_alias", ": Q", module="Library.P.F", rel=rel)
    monkeypatch.setattr(dedup, "_load_decls", lambda ws, p, si: ([a, b], []))
    monkeypatch.setattr(dedup, "_audit_one_file", lambda *ag, **k: ([], "log"))
    monkeypatch.setattr(dedup, "_classify_pairs", lambda *ag, **k: ({}, []))
    monkeypatch.setattr(dedup, "_cleanup_one_file", lambda *ag, **k: {
        "drops": {}, "merged": set(), "bridged": [(b.fqn, a)],
        "near": [], "failed": []})
    seen: dict = {}

    def _cap(stage, ret):
        def _f(ws, p, tf, decls, **k):
            seen[stage] = [d.name for d in decls]
            return ret
        return _f
    monkeypatch.setattr(dedup, "file_cleanup_polish", _cap("polish", False))
    monkeypatch.setattr(dedup, "file_cleanup_decide", _cap("decide", ({}, False)))
    monkeypatch.setattr(dedup, "file_cleanup_audit", _cap("audit", ({}, False)))
    res = dedup.run_staged_cleanup_file(
        tmp_path, "p", rel, bridge=False,
        polish=True, decide=True, audit=True)
    assert seen["polish"] == ["keep_me", "bridge_alias"]
    assert seen["decide"] == ["keep_me", "bridge_alias"]
    assert seen["audit"] == ["keep_me", "bridge_alias"]
    assert res["bridged"] == {b.fqn: a.fqn}


def test_replace_token_rewrites_dot_projection() -> None:
    # Dot-notation projection on the renamed decl MUST rewrite — the old name
    # ceases to exist, a left-behind `old.…` is a guaranteed dangle (stokes
    # bdry_manifold 2026-06-11: `smooth_face_proj.contDiffOn` survived the
    # deferred rename and broke the bridge build).
    from Tooling.quality.librarian.cleanup._common import replace_token
    assert replace_token("h := smooth_face_proj.contDiffOn.comp hmid",
                         "smooth_face_proj", "contDiff_faceProj") == \
        ("h := contDiff_faceProj.contDiffOn.comp hmid", 1)
    # FQN + projection
    assert replace_token("Library.X.foo.comp y", "Library.X.foo",
                         "Library.Y.bar") == ("Library.Y.bar.comp y", 1)
    # boundaries unchanged: FQN tail / longer identifier untouched
    assert replace_token("A.foo", "foo", "X")[1] == 0
    assert replace_token("fool x", "foo", "X")[1] == 0
    assert replace_token("xfoo", "foo", "X")[1] == 0
