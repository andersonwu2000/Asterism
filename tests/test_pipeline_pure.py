"""Pure functions in pipeline.py — no DB, no filesystem (mostly)."""
from __future__ import annotations

from pathlib import Path

import pytest

from Tooling.pipeline import (
    _is_sorry_stub,
    _replace_proof_body,
    _grep_forbidden,
    _extract_statement,
    _lean_path_to_module,
    _slug_from_filename,
)


# ---------------------------------------------------------------------
# _is_sorry_stub / _replace_proof_body
# ---------------------------------------------------------------------

def test_sorry_stub_canonical() -> None:
    assert _is_sorry_stub("theorem foo : Nat := by sorry\n")
    assert _is_sorry_stub("theorem foo : Nat := by sorry")


def test_sorry_stub_in_namespace() -> None:
    src = "namespace X\ntheorem foo : Nat := by sorry\nend X\n"
    assert _is_sorry_stub(src)


def test_sorry_stub_rejects_structured_patch() -> None:
    src = """theorem foo : Nat := by
  have h1 : Nat := L_sub_1
  exact h1
"""
    assert not _is_sorry_stub(src)


def test_sorry_stub_rejects_existing_proof() -> None:
    assert not _is_sorry_stub("theorem foo : Nat := by simp\n")


def test_replace_proof_body_keeps_trailing_newline() -> None:
    src = "theorem foo : Nat := by sorry\n"
    assert _replace_proof_body(src, "simp") == "theorem foo : Nat := by simp\n"


def test_replace_proof_body_strips_by_prefix() -> None:
    src = "theorem foo : Nat := by sorry\n"
    assert _replace_proof_body(src, "by aesop") == "theorem foo : Nat := by aesop\n"


# ---------------------------------------------------------------------
# _grep_forbidden
# ---------------------------------------------------------------------

def test_grep_forbidden_exact() -> None:
    assert _grep_forbidden("by exact ZMod.wilsons_lemma p hp", ["ZMod.wilsons_lemma"]) == "ZMod.wilsons_lemma"


def test_grep_forbidden_misses_substring() -> None:
    assert _grep_forbidden("by exact xZMod.wilsons_lemma_y", ["ZMod.wilsons_lemma"]) is None


def test_grep_forbidden_word_boundary() -> None:
    # the word boundary must reject `wilsons_lemma_extension`
    assert _grep_forbidden("wilsons_lemma_extension", ["wilsons_lemma"]) is None


def test_grep_forbidden_wildcard() -> None:
    assert _grep_forbidden("Mathlib.Wilson.theorem", ["Mathlib.*.theorem"]) == "Mathlib.*.theorem"


def test_grep_forbidden_returns_none_when_clean() -> None:
    assert _grep_forbidden("by simp", ["ZMod.wilsons_lemma"]) is None


# ---------------------------------------------------------------------
# _extract_statement
# ---------------------------------------------------------------------

@pytest.mark.parametrize("src,want", [
    ("theorem foo : Nat := by sorry", "Nat"),
    ("theorem foo (x : Nat) : x = x := by rfl", "x = x"),
    ("theorem foo {α : Type*} (x : α) : x = x := by rfl", "x = x"),
    ("theorem foo (h : x ≥ 0) (hy : y > 0) : x + y > 0 := by sorry", "x + y > 0"),
    ("theorem foo : ∀ p : ℕ, p.Prime → p ≥ 2 := by sorry", "∀ p : ℕ, p.Prime → p ≥ 2"),
    ("theorem foo [Inhabited α] : α := by exact default", "α"),
    ("theorem foo : (a : Nat) × (b : Nat) := by sorry", "(a : Nat) × (b : Nat)"),
    ("namespace X\ntheorem foo : True := trivial\nend X", "True"),
])
def test_extract_statement(src: str, want: str) -> None:
    assert _extract_statement(src) == want


def test_extract_statement_no_theorem() -> None:
    assert _extract_statement("def foo : Nat := 1") == ""


# ---------------------------------------------------------------------
# _lean_path_to_module / _slug_from_filename
# ---------------------------------------------------------------------

def test_lean_path_to_module(tmp_path: Path) -> None:
    workspace = tmp_path
    p = workspace / "Problems" / "wilson" / "Root.lean"
    assert _lean_path_to_module(workspace, p) == "Problems.wilson.Root"


def test_lean_path_to_module_nested(tmp_path: Path) -> None:
    workspace = tmp_path
    p = workspace / "Problems" / "wilson" / "proofs" / "L_main_sub_1.lean"
    assert _lean_path_to_module(workspace, p) == "Problems.wilson.proofs.L_main_sub_1"


def test_slug_from_filename() -> None:
    assert _slug_from_filename("new_main_sub_1.lean") == "main_sub_1"
    assert _slug_from_filename("foo.lean") == "foo"
