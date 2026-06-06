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
