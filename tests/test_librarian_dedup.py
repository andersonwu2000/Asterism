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
# code_token_invariant — the docstring (e) safety gate (P2a)
# ---------------------------------------------------------------------

def test_code_token_invariant_comment_only_change() -> None:
    old = "import Mathlib\ntheorem foo : True := by trivial\n"
    new = "import Mathlib\n/-- foo is true. -/\ntheorem foo : True := by trivial\n"
    assert dedup.code_token_invariant(old, new) is True


def test_code_token_invariant_detects_code_change() -> None:
    old = "theorem foo : True := by trivial\n"
    new = "/-- doc -/\ntheorem foo : True := by simp\n"   # tactic changed
    assert dedup.code_token_invariant(old, new) is False


def test_code_token_invariant_ignores_whitespace_in_comments() -> None:
    old = "theorem foo : True := by trivial\n"
    new = "theorem foo : True := by trivial  -- note\n\n"
    assert dedup.code_token_invariant(old, new) is True


# ---------------------------------------------------------------------
# file_cleanup_docstrings — (e) whole-file docstring pass with retry (P2a)
# ---------------------------------------------------------------------

def _setup_docstring(tmp_path, rel, content, *, prompt=True):
    if prompt:
        pd = tmp_path / "Tooling" / "prompts" / "librarian"
        pd.mkdir(parents=True, exist_ok=True)
        (pd / "docstring.md").write_text("polish docstrings", encoding="utf-8")
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


def _fake_spawn(monkeypatch, responses):
    """Patch agent.spawn_llm to write responses[i] (str|None) as annotated.lean
    on the i-th call; returns the call counter dict."""
    from Tooling import agent
    calls = {"n": 0}

    def _spawn(*, kind, prompt_path, problem_dir, attempts_dir, session_id):
        i = calls["n"]
        calls["n"] += 1
        if i < len(responses) and responses[i] is not None:
            (attempts_dir / "annotated.lean").write_text(
                responses[i], encoding="utf-8")
        return 0
    monkeypatch.setattr(agent, "spawn_llm", _spawn)
    return calls


_ORIG = "import Mathlib\ntheorem foo : True := by trivial\n"
_DOC = "import Mathlib\n/-- foo is true. -/\ntheorem foo : True := by trivial\n"


def test_file_cleanup_docstrings_success(tmp_path, monkeypatch) -> None:
    rel = "Library/P/F.lean"
    _setup_docstring(tmp_path, rel, _ORIG)
    _fake_spawn(monkeypatch, [_DOC])
    monkeypatch.setattr(dedup, "_build_file_copy_isolated",
                        lambda ws, txt, **k: (True, ""))
    assert dedup.file_cleanup_docstrings(tmp_path, "p", rel, ["foo"]) is True
    assert (tmp_path / rel).read_text(encoding="utf-8") == _DOC


def test_file_cleanup_docstrings_rejects_code_change(tmp_path, monkeypatch) -> None:
    rel = "Library/P/F.lean"
    _setup_docstring(tmp_path, rel, _ORIG)
    bad = "import Mathlib\ntheorem foo : True := by simp\n"     # code touched
    calls = _fake_spawn(monkeypatch, [bad, bad, bad])
    monkeypatch.setattr(dedup, "_build_file_copy_isolated",
                        lambda ws, txt, **k: (True, ""))
    assert dedup.file_cleanup_docstrings(
        tmp_path, "p", rel, ["foo"], max_retries=2) is False
    assert (tmp_path / rel).read_text(encoding="utf-8") == _ORIG   # untouched
    assert calls["n"] == 3                                         # retried


def test_file_cleanup_docstrings_build_fail_keeps_original(tmp_path, monkeypatch) -> None:
    rel = "Library/P/F.lean"
    _setup_docstring(tmp_path, rel, _ORIG)
    _fake_spawn(monkeypatch, [_DOC, _DOC, _DOC])
    monkeypatch.setattr(dedup, "_build_file_copy_isolated",
                        lambda ws, txt, **k: (False, "parse error"))
    assert dedup.file_cleanup_docstrings(
        tmp_path, "p", rel, ["foo"], max_retries=2) is False
    assert (tmp_path / rel).read_text(encoding="utf-8") == _ORIG


def test_file_cleanup_docstrings_retry_then_success(tmp_path, monkeypatch) -> None:
    rel = "Library/P/F.lean"
    _setup_docstring(tmp_path, rel, _ORIG)
    bad = "import Mathlib\ntheorem foo : True := by simp\n"
    _fake_spawn(monkeypatch, [bad, _DOC])           # 1st rejected, 2nd accepted
    monkeypatch.setattr(dedup, "_build_file_copy_isolated",
                        lambda ws, txt, **k: (True, ""))
    assert dedup.file_cleanup_docstrings(
        tmp_path, "p", rel, ["foo"], max_retries=2) is True
    assert (tmp_path / rel).read_text(encoding="utf-8") == _DOC


def test_file_cleanup_docstrings_noop_when_prompt_absent(tmp_path, monkeypatch) -> None:
    rel = "Library/P/F.lean"
    _setup_docstring(tmp_path, rel, _ORIG, prompt=False)     # no prompt file
    called = _fake_spawn(monkeypatch, [_DOC])
    assert dedup.file_cleanup_docstrings(tmp_path, "p", rel, ["foo"]) is False
    assert called["n"] == 0                                  # never spawned
    assert (tmp_path / rel).read_text(encoding="utf-8") == _ORIG


def test_file_cleanup_docstrings_noop_when_unchanged(tmp_path, monkeypatch) -> None:
    # agent returns the file verbatim → nothing to do, no write, no build.
    rel = "Library/P/F.lean"
    _setup_docstring(tmp_path, rel, _ORIG)
    _fake_spawn(monkeypatch, [_ORIG])
    built = {"n": 0}

    def _b(ws, txt, **k):
        built["n"] += 1
        return (True, "")
    monkeypatch.setattr(dedup, "_build_file_copy_isolated", _b)
    assert dedup.file_cleanup_docstrings(tmp_path, "p", rel, ["foo"]) is False
    assert built["n"] == 0                                   # skipped the build


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
    assert dedup._parse_simplify_marks('["a","b"]') == {"a", "b"}
    assert dedup._parse_simplify_marks('[{"decl":"a"},{"decl":"b"}]') == {"a", "b"}
    assert dedup._parse_simplify_marks("not json") == set()


def test_simplify_success_replaces_only_marked(tmp_path, monkeypatch) -> None:
    rel = "Library/P/F.lean"
    _setup_simplify(tmp_path, rel, _FILE2)
    _fake_simplify_spawn(monkeypatch, ["by simp"])
    monkeypatch.setattr(dedup, "_build_decl_isolated", lambda ws, **k: (True, ""))
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
    monkeypatch.setattr(dedup, "_build_decl_isolated", lambda ws, **k: (True, ""))
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
    monkeypatch.setattr(dedup, "_build_decl_isolated", _b)
    assert dedup.decl_cleanup_simplify_file(
        tmp_path, "p", rel, [_decl("foo")], {"foo"}) == 0
    assert built["n"] == 0


def test_simplify_build_fail_keeps_original(tmp_path, monkeypatch) -> None:
    rel = "Library/P/F.lean"
    _setup_simplify(tmp_path, rel, _FILE2)
    _fake_simplify_spawn(monkeypatch, ["by simp", "by simp", "by simp"])
    monkeypatch.setattr(dedup, "_build_decl_isolated",
                        lambda ws, **k: (False, "boom"))
    assert dedup.decl_cleanup_simplify_file(
        tmp_path, "p", rel, [_decl("foo")], {"foo"}, max_retries=2) == 0
    assert (tmp_path / rel).read_text(encoding="utf-8") == _FILE2


def test_simplify_retry_then_success(tmp_path, monkeypatch) -> None:
    rel = "Library/P/F.lean"
    _setup_simplify(tmp_path, rel, _FILE2)
    _fake_simplify_spawn(monkeypatch, ["by bad", "by simp"])
    seq = iter([(False, "err"), (True, "")])
    monkeypatch.setattr(dedup, "_build_decl_isolated", lambda ws, **k: next(seq))
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
    assert dedup._mark_simplify_file(
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
    assert dedup._strip_json_fence('[{"x":"a"}]') == '[{"x":"a"}]'


def test_strip_json_fence_fenced() -> None:
    assert dedup._strip_json_fence('```json\n[{"x":"a"}]\n```') == '[{"x":"a"}]'
    assert dedup._strip_json_fence('```\n[]\n```') == '[]'


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
    assert (dedup._norm_type("∀ {K : Type u_1}  {V : Type u_2},\n  P")
            == "∀ {K : Type u} {V : Type u}, P")


def _setup_var(tmp_path, rel, content, *, prompt="variable_extract.md"):
    if prompt:
        pd = tmp_path / "Tooling" / "prompts" / "librarian"
        pd.mkdir(parents=True, exist_ok=True)
        (pd / prompt).write_text("x", encoding="utf-8")
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def _fake_var_spawn(monkeypatch, outputs):
    """Patch agent.spawn_llm to write outputs[i] (str|None) as refactored.lean."""
    from Tooling import agent
    calls = {"n": 0}

    def _spawn(*, kind, prompt_path, problem_dir, attempts_dir, session_id):
        i = calls["n"]
        calls["n"] += 1
        o = outputs[i] if i < len(outputs) else None
        if o is not None:
            (attempts_dir / "refactored.lean").write_text(o, encoding="utf-8")
        return 0
    monkeypatch.setattr(agent, "spawn_llm", _spawn)
    return calls


def _fake_typecheck(monkeypatch, results):
    seq = {"n": 0}

    def _tc(ws, text, fqns, **k):
        i = seq["n"]
        seq["n"] += 1
        return results[i]
    monkeypatch.setattr(dedup, "_typecheck_capturing_types", _tc)
    return seq


def test_file_cleanup_variables_noop_without_prompt(tmp_path) -> None:
    rel = "Library/P/F.lean"
    _setup_var(tmp_path, rel, "import Mathlib\n", prompt=None)   # no prompt file
    d = _vdecl("foo", ": ∀ {K : Type*}, P")
    assert dedup.file_cleanup_variables(tmp_path, "p", rel, [d]) is False


def test_file_cleanup_variables_skip_when_idiomatic(tmp_path, monkeypatch) -> None:
    rel = "Library/P/F.lean"
    _setup_var(tmp_path, rel, "import Mathlib\n")
    spy = _fake_var_spawn(monkeypatch, [])
    d = _vdecl("foo", "(a : T) : P")            # not prenex, single decl → nothing
    assert dedup.file_cleanup_variables(tmp_path, "p", rel, [d]) is False
    assert spy["n"] == 0                         # pre-filter skipped before spawn


def test_file_cleanup_variables_skip_when_no_snapshot(tmp_path, monkeypatch) -> None:
    rel = "Library/P/F.lean"
    _setup_var(tmp_path, rel, "import Mathlib\n")
    spy = _fake_var_spawn(monkeypatch, ["whatever"])
    _fake_typecheck(monkeypatch, [(False, "snapshot build broke", {})])
    d = _vdecl("foo", ": ∀ {K : Type*}, P")
    assert dedup.file_cleanup_variables(tmp_path, "p", rel, [d]) is False
    assert spy["n"] == 0                         # never spawned without a baseline


def test_file_cleanup_variables_success(tmp_path, monkeypatch) -> None:
    rel = "Library/P/F.lean"
    _setup_var(tmp_path, rel, "import Mathlib\n-- orig\n")
    d = _vdecl("foo", ": ∀ {K : Type*} [Field K], P")
    new = "import Mathlib\nvariable {K : Type*} [Field K]\n-- refactored\n"
    _fake_var_spawn(monkeypatch, [new])
    _fake_typecheck(monkeypatch, [(True, "", {d.fqn: "T"}),    # snapshot
                                  (True, "", {d.fqn: "T"})])   # post: same type
    assert dedup.file_cleanup_variables(tmp_path, "p", rel, [d]) is True
    assert (tmp_path / rel).read_text(encoding="utf-8") == new


def _json_info(data):
    import json
    return json.dumps({"severity": "information", "data": data})


def test_parse_check_output_at_prefixed() -> None:
    out = _json_info("@L.A.foo : ∀ {n : ℕ}, n = n")
    types, errs = dedup._parse_check_output(out, ["L.A.foo"])
    assert errs == [] and types == {"L.A.foo": "∀ {n : ℕ}, n = n"}


def test_parse_check_output_no_at_when_no_implicit() -> None:
    # Lean drops the `@` for a decl with only explicit binders (the bug that
    # skipped whole files: parser matched only `@foo :`).
    out = _json_info("L.A.foo : ∀ (S : T), P S")
    types, _ = dedup._parse_check_output(out, ["L.A.foo"])
    assert types == {"L.A.foo": "∀ (S : T), P S"}


def test_parse_check_output_universe_annotation() -> None:
    out = _json_info("@L.A.foo.{u_1} : Type u_1 → Type u_1")
    types, _ = dedup._parse_check_output(out, ["L.A.foo"])
    assert types == {"L.A.foo": "Type u → Type u"}        # u_1 normalized


def test_parse_check_output_no_prefix_collision() -> None:
    out = "\n".join([_json_info("@L.A.foo_bar : Bar"), _json_info("@L.A.foo : Foo")])
    types, _ = dedup._parse_check_output(out, ["L.A.foo", "L.A.foo_bar"])
    assert types == {"L.A.foo": "Foo", "L.A.foo_bar": "Bar"}


def test_parse_check_output_collects_errors() -> None:
    import json
    out = json.dumps({"severity": "error", "data": "unknown identifier 'baz'"})
    types, errs = dedup._parse_check_output(out, ["L.A.foo"])
    assert types == {} and errs == ["unknown identifier 'baz'"]


def test_file_cleanup_variables_reverts_on_sig_change(tmp_path, monkeypatch) -> None:
    rel = "Library/P/F.lean"
    original = "import Mathlib\n-- orig\n"
    _setup_var(tmp_path, rel, original)
    d = _vdecl("foo", ": ∀ {K : Type*}, P")
    _fake_var_spawn(monkeypatch, ["v1\n", "v2\n", "v3\n"])     # 1 + 2 retries
    _fake_typecheck(monkeypatch, [(True, "", {d.fqn: "T"})]    # snapshot
                    + [(True, "", {d.fqn: "CHANGED"})] * 3)    # type drifts each try
    assert dedup.file_cleanup_variables(tmp_path, "p", rel, [d]) is False
    assert (tmp_path / rel).read_text(encoding="utf-8") == original   # kept
