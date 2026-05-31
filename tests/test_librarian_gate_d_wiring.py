"""Gate D wiring on the migrate path — decl-kind detection, Library
module mapping, and the def-tampering guard (librarian.migrate_defeq_gate).

All gateway-free: migrate_defeq_gate's rfl check is exercised through the
injectable `defeq_verifier`, so no Lean build runs here."""
from __future__ import annotations

from Tooling.pipeline import librarian as lib


# ---------------------------------------------------------------------
# extract_decl_kind
# ---------------------------------------------------------------------

def test_extract_decl_kind_def():
    assert lib.extract_decl_kind("namespace A\ndef foo : Nat := 0") == "def"


def test_extract_decl_kind_abbrev():
    assert lib.extract_decl_kind("abbrev foo := 0") == "abbrev"


def test_extract_decl_kind_theorem():
    assert lib.extract_decl_kind("theorem t : True := trivial") == "theorem"


def test_extract_decl_kind_structure():
    assert lib.extract_decl_kind(
        "structure S where\n  x : Nat") == "structure"


def test_extract_decl_kind_inductive():
    # inductive isn't in the shared _DECL_KW (axiom path) but Gate D's
    # nominal check must still recognise it.
    assert lib.extract_decl_kind("inductive I\n  | a") == "inductive"


def test_extract_decl_kind_skips_modifiers():
    assert lib.extract_decl_kind("noncomputable def f := 0") == "def"


def test_extract_decl_kind_none():
    assert lib.extract_decl_kind("-- comment\nimport Mathlib") is None


# ---------------------------------------------------------------------
# _library_module_of
# ---------------------------------------------------------------------

def test_library_module_of_posix():
    assert lib._library_module_of(
        "Library/LinearAlgebra/JordanForm/Defs.lean"
    ) == "Library.LinearAlgebra.JordanForm.Defs"


def test_library_module_of_windows_sep():
    assert lib._library_module_of("Library\\A\\Basic.lean") == "Library.A.Basic"


# ---------------------------------------------------------------------
# migrate_defeq_gate (Gate D for the migrate path)
# ---------------------------------------------------------------------

_DEF = "namespace Library.A\ndef IsFoo : Prop := True"


def _never(_probe):
    raise AssertionError("defeq verifier should not be called")


def test_defeq_gate_skips_non_defs_decl():
    """A migrated lemma (slug not among the problem's Defs decls) bypasses
    Gate D entirely — only `def` bodies need the tamper pin."""
    r = lib.migrate_defeq_gate(
        "namespace Library.A\ntheorem bar : True := trivial",
        problem="p", target_slug="bar", defs_decls=["IsFoo"],
        target_module="Library.A.Basic", defeq_verifier=_never)
    assert r.ok, r.detail


def test_defeq_gate_def_passes_when_rfl_ok():
    r = lib.migrate_defeq_gate(
        _DEF, problem="p", target_slug="IsFoo", defs_decls=["IsFoo"],
        target_module="Library.A.Basic",
        defeq_verifier=lambda _p: (True, ""))
    assert r.ok, r.detail


def test_defeq_gate_def_fails_when_rfl_fails():
    r = lib.migrate_defeq_gate(
        _DEF, problem="p", target_slug="IsFoo", defs_decls=["IsFoo"],
        target_module="Library.A.Basic",
        defeq_verifier=lambda _p: (False, "not defeq"))
    assert not r.ok
    assert "IsFoo" in r.detail


def test_defeq_gate_nominal_structure_declines():
    r = lib.migrate_defeq_gate(
        "namespace Library.A\nstructure IsFoo where\n  x : Nat",
        problem="p", target_slug="IsFoo", defs_decls=["IsFoo"],
        target_module="Library.A.Basic", defeq_verifier=_never)
    assert not r.ok
    assert "nominal" in r.detail and "structure" in r.detail


def test_defeq_gate_nominal_inductive_declines():
    r = lib.migrate_defeq_gate(
        "namespace Library.A\ninductive IsFoo\n  | a",
        problem="p", target_slug="IsFoo", defs_decls=["IsFoo"],
        target_module="Library.A.Basic", defeq_verifier=_never)
    assert not r.ok
    assert "inductive" in r.detail


def test_defeq_gate_unextractable_name_fails():
    """A Defs decl whose patch has no parseable declaration name is
    rejected, not silently passed."""
    r = lib.migrate_defeq_gate(
        "namespace Library.A\n-- nothing here",
        problem="p", target_slug="IsFoo", defs_decls=["IsFoo"],
        target_module="Library.A.Basic", defeq_verifier=_never)
    assert not r.ok
