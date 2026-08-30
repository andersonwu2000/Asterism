"""A sub-goal stub declares exactly one thing (owner ruling 2026-08-30,
task #231 fix 3).

Backward's skeleton carries the parent's preamble (imports / opens /
variables) into each sub-goal stub so the statement elaborates
standalone — a deliberate choice (`_skeleton.py`, agent_feedback T2/
T13). Helper `def`s and `instance`s the agent wrote to STATE a sub-goal
rode along the same way, and the promotion to `def <slug> := @s<N>`
keeps only the imports: the helper vanishes and every strategy that
cited it breaks (seven at one promotion on 2026-08-28; `fin5_weight`,
`Fintype fin4_family`, `six_point_row_zero_encode`). One brick, one
declaration: a helper is its own brick or lives in Defs.lean.
"""
from __future__ import annotations

from Tooling.state import assemble, failures


def test_extra_decls_names_everything_but_the_stub_itself():
    stub = (
        "import Mathlib\n\n"
        "namespace Problems.p\n\n"
        "def fin5_weight (F : Finset (Finset (Fin 5))) : ℕ := F.card\n\n"
        "instance : Fintype fin4_family := by infer_instance\n\n"
        "theorem atom_weight_bound : fin5_weight ∅ ≤ 22 := by sorry\n\n"
        "end Problems.p\n"
    )
    assert assemble.extra_decls(stub, "atom_weight_bound") == ["fin5_weight", "<instance>"]


def test_extra_decls_is_empty_for_a_clean_stub():
    stub = ("import Mathlib\nopen Finset\n\nnamespace Problems.p\n\n"
            "set_option linter.unusedVariables false in\n"
            "theorem atom_weight_bound (n : ℕ) : n ≤ n := by sorry\n\nend Problems.p\n")
    assert assemble.extra_decls(stub, "atom_weight_bound") == []


def test_extra_decls_ignores_commented_declarations():
    stub = ("import Mathlib\n-- def helper := 1\n/- instance : Foo := bar -/\n"
            "theorem t : True := by sorry\n")
    assert assemble.extra_decls(stub, "t") == []


def test_stub_extra_decls_is_a_registered_failure_reason():
    assert "stub_extra_decls" in failures.REGISTRY


def test_stub_extra_decls_message_names_the_way_out():
    msg = assemble.extra_decls_message("atom_weight_bound", ["fin5_weight", "<instance>"])
    assert "fin5_weight" in msg
    assert "own brick" in msg or "Defs.lean" in msg, "the gate names a reachable action"
