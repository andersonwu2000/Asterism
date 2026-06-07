"""Token-aware reference rewrite for PHASE 3 cleanup-dedup v1a (task #109)."""
from __future__ import annotations

from Tooling.quality.librarian import dedup


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


def test_fqn_not_matched_when_extended() -> None:
    # `Library.A.foo.comp` must not be partially rewritten.
    out, n = dedup.replace_token("Library.A.foo.comp", "Library.A.foo", "Library.B.bar")
    assert out == "Library.A.foo.comp"
    assert n == 0


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
    spans = dedup._code_spans(text)
    # concatenating the code spans + the gaps must reconstruct the text
    assert spans[0][0] == 0
    assert spans[-1][1] == len(text)
    # code spans never overlap a comment marker's interior
    for s, e in spans:
        assert "-- " not in text[s:e]


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
# v1b-① — parse_dedup_pairs / _strip_json_fence / mark_context
# ---------------------------------------------------------------------

def test_strip_json_fence_plain() -> None:
    assert dedup._strip_json_fence('[{"x":"a"}]') == '[{"x":"a"}]'


def test_strip_json_fence_fenced() -> None:
    assert dedup._strip_json_fence('```json\n[{"x":"a"}]\n```') == '[{"x":"a"}]'
    assert dedup._strip_json_fence('```\n[]\n```') == '[]'


def test_parse_dedup_pairs_ok() -> None:
    txt = ('[{"x":"L.A.foo","y":"L.B.bar","kind":"exact","why":"same"},'
           ' {"x":"L.A.baz","y":"L.C.qux","kind":"near","why":"bridge"}]')
    pairs, err = dedup.parse_dedup_pairs(txt)
    assert err == ""
    assert pairs == [("L.A.foo", "L.B.bar"), ("L.A.baz", "L.C.qux")]


def test_parse_dedup_pairs_empty_array() -> None:
    pairs, err = dedup.parse_dedup_pairs("[]")
    assert err == "" and pairs == []


def test_parse_dedup_pairs_fenced() -> None:
    pairs, err = dedup.parse_dedup_pairs('```json\n[{"x":"a","y":"b"}]\n```')
    assert err == "" and pairs == [("a", "b")]


def test_parse_dedup_pairs_bad_json() -> None:
    pairs, err = dedup.parse_dedup_pairs("not json")
    assert pairs is None and "valid JSON" in err


def test_parse_dedup_pairs_not_array() -> None:
    pairs, err = dedup.parse_dedup_pairs('{"x":"a","y":"b"}')
    assert pairs is None and "array" in err


def test_parse_dedup_pairs_missing_key() -> None:
    pairs, err = dedup.parse_dedup_pairs('[{"x":"a"}]')
    assert pairs is None and "missing" in err


def test_parse_dedup_pairs_nonstring_value() -> None:
    pairs, err = dedup.parse_dedup_pairs('[{"x":"a","y":3}]')
    assert pairs is None and "strings" in err


_INDEX = (
    "## LinearAlgebra.p1\n"
    "- `Library.LinearAlgebra.P1.F.foo` → `Library/LinearAlgebra/P1/F.lean`\n"
    "## LinearAlgebra.p2\n"
    "- `Library.LinearAlgebra.P2.G.bar` → `Library/LinearAlgebra/P2/G.lean`\n"
)


def test_mark_context_lists_scope_and_pool(tmp_path) -> None:
    _mk_lib(tmp_path, {
        "Library/INDEX.md": _INDEX,
        "Library/LinearAlgebra/P1/F.lean":
            "import Mathlib\ntheorem foo (n : Nat) : n = n := by rfl\n",
        "Library/LinearAlgebra/P2/G.lean":
            "import Mathlib\ntheorem bar (m : Nat) : m = m := by rfl\n",
    })
    out = dedup.mark_context(tmp_path, "LinearAlgebra.p1")
    assert "# dedup marking — LinearAlgebra.p1" in out
    assert "SCOPE (1 decls)" in out and "POOL (2 decls)" in out
    # scope decl present with its signature
    assert "Library.LinearAlgebra.P1.F.foo :: (n : Nat) : n = n" in out
    # same-domain pool includes both p1 and p2 decls
    assert "Library.LinearAlgebra.P2.G.bar :: (m : Nat) : m = m" in out


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
    assert s[dedup._proof_assign_pos(s, 0):][:2] == ":="


def test_proof_assign_pos_skips_binder_default() -> None:
    # the `:=` inside `(x : Nat := 0)` (depth>0) must be skipped; the proof
    # `:=` is the first at depth 0.
    s = "theorem f (x : Nat := 0) : T := pf"
    p = dedup._proof_assign_pos(s, 0)
    assert s[p:] == ":= pf"


def test_proof_assign_pos_skips_structure_instance() -> None:
    s = "theorem f : T := by exact { a := 1 }"
    p = dedup._proof_assign_pos(s, 0)
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
