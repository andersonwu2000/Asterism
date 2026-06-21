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
    # inductive is a recognised decl keyword so Gate D's nominal check sees
    # it (and the positional per-file pairing counts it as a declaration).
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


def test_defeq_gate_preserved_namespace_defs_uses_source_equality(tmp_path):
    # #43: a Defs decl the operator authored under a foreign namespace
    # (`Complex.windingNumber`) keeps that FQN in the Library, so
    # defs_fq == target_fq. The cross-module defeq probe would import BOTH the
    # problem Defs and the Library copy → "environment already contains
    # 'Complex.windingNumber'" (the residue migrate STALL). Gate D must verify
    # by verbatim SOURCE equality instead — the injected defeq verifier must
    # NEVER run (proving the dual-import probe is skipped).
    from Tooling.state import db as _db
    decl = "noncomputable def windingNumber (n : Nat) : Nat :=\n  0"
    body = f"import Mathlib\n\nnamespace Complex\n\n{decl}\n\nend Complex\n"
    defs = _db.problem_dir(tmp_path, "residue_thm") / "Defs.lean"
    defs.parent.mkdir(parents=True, exist_ok=True)
    defs.write_text(body, encoding="utf-8")
    r = lib.migrate_defeq_gate(
        body, problem="residue_thm", target_slug="windingNumber",
        defs_decls=["windingNumber"],
        target_module="Library.Analysis.ResidueThm.CircleIntegral",
        workspace=tmp_path, defeq_verifier=_never)
    assert r.ok, r.detail            # source-equal → passes without the probe


def test_defeq_gate_unextractable_name_fails():
    """A Defs decl whose patch has no parseable declaration name is
    rejected, not silently passed."""
    r = lib.migrate_defeq_gate(
        "namespace Library.A\n-- nothing here",
        problem="p", target_slug="IsFoo", defs_decls=["IsFoo"],
        target_module="Library.A.Basic", defeq_verifier=_never)
    assert not r.ok


# ---------------------------------------------------------------------
# _defs_decl_fqn — real FQN of a Defs decl (foreign-namespace aware)
# ---------------------------------------------------------------------

_FOREIGN_DEFS = (
    "import Mathlib\n\n"
    "namespace Complex\n\n"
    "noncomputable def windingNumber (g : ℝ → ℂ) (a : ℂ) : ℤ := 0\n\n"
    "noncomputable def residue (f : ℂ → ℂ) (z : ℂ) : ℂ := 0\n\n"
    "end Complex\n")


def test_defs_decl_fqn_foreign_namespace():
    # residue_thm declares windingNumber/residue under `namespace Complex`, so
    # the real FQN is `Complex.windingNumber`, NOT the naive
    # `Problems.residue_thm.windingNumber` (an unknown identifier → STALL).
    assert lib._defs_decl_fqn(_FOREIGN_DEFS, "windingNumber",
                              problem="residue_thm") == "Complex.windingNumber"
    assert lib._defs_decl_fqn(_FOREIGN_DEFS, "residue",
                              problem="residue_thm") == "Complex.residue"


def test_defs_decl_fqn_standard_namespace():
    txt = "namespace Problems.p\n\ndef foo : Nat := 0\n\nend Problems.p\n"
    assert lib._defs_decl_fqn(txt, "foo", problem="p") == "Problems.p.foo"


def test_defs_decl_fqn_fallback_when_absent():
    # Not found in Defs → historical default (no regression for the common
    # in-`Problems`-namespace case).
    assert lib._defs_decl_fqn("-- empty\n", "foo", problem="p") == "Problems.p.foo"


def test_defeq_gate_uses_real_fqn_for_foreign_namespace(tmp_path):
    # End-to-end: with a foreign-namespace Defs decl, the probe must reference
    # `Complex.windingNumber`, not the naive `Problems.residue_thm.windingNumber`
    # (the bug that STALLed WindingNumberContinuity). Capture the probe text.
    pd = tmp_path / "Problems" / "residue_thm"
    pd.mkdir(parents=True)
    (pd / "Defs.lean").write_text(_FOREIGN_DEFS, encoding="utf-8")
    seen = {}

    def _capture(probe):
        seen["probe"] = probe
        return True, ""
    r = lib.migrate_defeq_gate(
        "namespace Library.A\ndef windingNumber : Nat := 0",
        problem="residue_thm", target_slug="windingNumber",
        defs_decls=["windingNumber"], target_module="Library.A.Basic",
        defeq_verifier=_capture, workspace=tmp_path)
    assert r.ok, r.detail
    assert "Complex.windingNumber" in seen["probe"]
    assert "Problems.residue_thm.windingNumber" not in seen["probe"]
