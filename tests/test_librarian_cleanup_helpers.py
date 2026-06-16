"""Cleanup-stage helpers — the Mathlib-PR warning gate + variable-block tidy.

`_all_warnings` is the zero-warning bar the per-file cleanup gate enforces
(broader than polish's type-preserving subset — it must catch `deprecated`,
which core-Lean always emits and the old curated regex missed).
`_collapse_redundant_variable_blocks` drops the duplicate `variable` blocks the
per-decl migrate assembly replays, scope-safely.
"""
from __future__ import annotations

from Tooling.quality.librarian.cleanup import _common as C


# ---------------------------------------------------------------------
# _all_warnings — every `warning:` line, deduped
# ---------------------------------------------------------------------

def test_all_warnings_catches_deprecated_and_lints():
    out = (
        "Foo.lean:3:0: warning: `EuclideanSpace.single_apply` has been "
        "deprecated: use `PiLp.single_apply`\n"
        "Foo.lean:9:8: warning: unused variable `h`\n"
        "Foo.lean:1:0: warning: linter.style.longFile: file exceeds 1500 lines\n"
    )
    ws = C._all_warnings(out)
    assert len(ws) == 3
    assert any("deprecated" in w for w in ws)
    assert any("unused variable" in w for w in ws)


def test_all_warnings_dedups_and_empty_on_clean():
    dup = "x.lean:1:0: warning: unused variable `h`\n" * 3
    assert len(C._all_warnings(dup)) == 1
    assert C._all_warnings("Build completed successfully.\n") == []


# ---------------------------------------------------------------------
# _collapse_redundant_variable_blocks — scope-safe duplicate removal
# ---------------------------------------------------------------------

_VAR = ("variable {d : Nat}\n"
        "  {I : Bar d}\n"
        "  {N : Type}")


def test_collapse_adjacent_identical_block():
    # The StokesIntegralDefs:24/29 shape — two identical blocks, only a blank
    # between → the second is a no-op re-declaration, dropped.
    text = f"class Foo where\n  x : Nat\n\n{_VAR}\n\n{_VAR}\n\ndef t := 0\n"
    out = C._collapse_redundant_variable_blocks(text)
    assert out.count("variable {d : Nat}") == 1
    assert "def t := 0" in out and "class Foo" in out


def test_keep_duplicate_when_decl_between():
    # A declaration between the two blocks breaks adjacency → keep both
    # (conservative: only adjacent no-ops collapse).
    text = f"{_VAR}\n\ndef a := 0\n\n{_VAR}\n\ndef b := 0\n"
    assert C._collapse_redundant_variable_blocks(text).count(
        "variable {d : Nat}") == 2


def test_keep_duplicate_after_scope_end():
    # An `end` closes the first block's scope; the second is a real re-open.
    text = (f"section\n{_VAR}\ndef a := 0\nend\n\n{_VAR}\ndef b := 0\n")
    assert C._collapse_redundant_variable_blocks(text).count(
        "variable {d : Nat}") == 2


def test_keep_distinct_adjacent_blocks():
    text = "variable {d : Nat}\n\nvariable {e : Nat}\n\ndef a := 0\n"
    out = C._collapse_redundant_variable_blocks(text)
    assert "variable {d : Nat}" in out and "variable {e : Nat}" in out


def test_noop_without_duplicates():
    text = f"{_VAR}\n\ndef a := 0\n"
    assert C._collapse_redundant_variable_blocks(text) == text
