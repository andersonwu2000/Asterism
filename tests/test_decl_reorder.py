"""Post-cleanup intra-file decl reorder (`_reorder_decls_by_intrafile_refs`).

Closes the file_order-frozen-at-classify gap: cleanup (dedup/simplify) can
rewrite a proof to cite a sibling, introducing an intra-file dependency the
classify-time (import-based) usage graph never saw, leaving a forward
reference that fails the whole-Library build (eckart_young: termwise rewired
to cite eigen_pointwise + its helpers dropped). The reorder reads the FINAL
file's references and topologically reorders.
"""
from __future__ import annotations

from Tooling.pipeline.librarian import _reorder_decls_by_intrafile_refs as _reorder
from Tooling.quality.librarian.cleanup._common import _DECL_NAME_RE


def _order(text: str) -> list[str]:
    return [h.group(1) for h in _DECL_NAME_RE.finditer(text)]


def test_fixes_forward_reference():
    text = (
        "import Mathlib\n"
        "namespace N\n"
        "\n"
        "theorem uses_helper : True := helper_lemma\n"
        "\n"
        "theorem helper_lemma : True := trivial\n"
        "\n"
        "end N\n")
    out = _reorder(text)
    assert _order(out) == ["helper_lemma", "uses_helper"]
    # pure reorder: same decls, no text loss, header + footer intact
    assert out.startswith("import Mathlib\nnamespace N\n")
    assert out.rstrip().endswith("end N")
    assert len(out) == len(text)


def test_fqn_reference_detected():
    text = (
        "import Mathlib\n"
        "namespace N\n"
        "\n"
        "theorem uses_helper : True := N.helper_lemma\n"
        "\n"
        "theorem helper_lemma : True := trivial\n"
        "\n"
        "end N\n")
    assert _order(_reorder(text)) == ["helper_lemma", "uses_helper"]


def test_already_sound_is_noop():
    text = (
        "import Mathlib\n"
        "namespace N\n"
        "\n"
        "theorem helper_lemma : True := trivial\n"
        "\n"
        "theorem uses_helper : True := helper_lemma\n"
        "\n"
        "end N\n")
    assert _reorder(text) == text


def test_comment_mention_is_not_an_edge():
    # `helper_lemma` named only in a comment of `aaa` → stripped → no edge →
    # order unchanged (aaa stays first, even though it textually precedes the
    # helper's definition).
    text = (
        "import Mathlib\n"
        "namespace N\n"
        "\n"
        "theorem aaa : True := trivial  -- compare via helper_lemma\n"
        "\n"
        "theorem helper_lemma : True := trivial\n"
        "\n"
        "end N\n")
    assert _reorder(text) == text


def test_substring_name_not_a_false_edge():
    # `uses` cites `foo_2`, not `foo`; \bfoo\b must not match inside `foo_2`,
    # so `foo` is NOT forced before `uses`.
    text = (
        "import Mathlib\n"
        "namespace N\n"
        "\n"
        "theorem uses : True := foo_2\n"
        "\n"
        "theorem foo : True := trivial\n"
        "\n"
        "theorem foo_2 : True := trivial\n"
        "\n"
        "end N\n")
    out = _order(_reorder(text))
    # foo_2 (cited) must precede uses; foo (not cited) is unconstrained.
    assert out.index("foo_2") < out.index("uses")


def test_skips_file_with_structure():
    # A structure head is not sliced by _DECL_NAME_RE → mis-slice risk → SKIP.
    text = (
        "import Mathlib\n"
        "namespace N\n"
        "\n"
        "theorem uses_helper : True := helper_lemma\n"
        "\n"
        "structure Foo where\n"
        "  x : Nat\n"
        "\n"
        "theorem helper_lemma : True := trivial\n"
        "\n"
        "end N\n")
    assert _reorder(text) == text


def test_skips_on_duplicate_names():
    text = (
        "import Mathlib\n"
        "namespace N\n"
        "\n"
        "theorem a : True := b\n"
        "\n"
        "theorem b : True := trivial\n"
        "\n"
        "theorem b : True := trivial\n"     # duplicate (ambiguous slicing)
        "\n"
        "end N\n")
    assert _reorder(text) == text


def test_single_decl_is_noop():
    text = "import Mathlib\nnamespace N\n\ntheorem solo : True := trivial\n\nend N\n"
    assert _reorder(text) == text
