/-
  Sandbox disproof of the minif2f-transcribed statement of `imo_1962_p4`.

  ## Background
  Statement (as imported):
    ∀ (S : Set ℝ) (h₀ : S = { x : ℝ | Real.cos x ^ 2 + Real.cos (2 * x) ^ 2
                                     + Real.cos (3 * x) ^ 2 = 1 }),
      S = { x : ℝ | ∃ m : ℤ,
            x = π / 2 + m * π
          ∨ x = π / 4 + m * π / 2
          ∨ x = π / 6 + m * π / 6
          ∨ x = 5 * π / 6 + m * π / 6 }

  ## Bug
  The third and fourth branches of the answer set use step `π / 6`, but
  the IMO 1962 #4 solution `cos(3x) = 0` requires step `π / 3` (since
  `3x = π/2 + kπ` ⇒ `x = π/6 + kπ/3`). The over-fine step admits
  non-solutions like `x = 0` (= π/6 + (-1)·π/6).

  ## Counterexample
  Take S = { x | cos²x + cos²(2x) + cos²(3x) = 1 }, x = 0:
    x ∈ RHS:  third branch with m = -1 gives π/6 + (-1)·π/6 = 0 ✓
    x ∉ LHS:  cos²(0) + cos²(0) + cos²(0) = 1 + 1 + 1 = 3 ≠ 1 ✗
  Hence S ≠ RHS, so the universally-quantified equality fails.

  Note: facebookresearch/miniF2F merged PR #36 fixing this in their fork,
  but yangky11/miniF2F-lean4 (and the original openai/miniF2F that our
  adapter pulls from) still ships the broken version.

  ## How to verify
    cd D:/Asterism
    lake env lean docs/errata/minif2f/imo_1962_p4_disproof.lean
  Expected: clean elaboration; axioms = [propext, Classical.choice, Quot.sound].
-/
import Mathlib

open Real

namespace Minif2fErrata.Imo1962P4

def stmt : Prop :=
  ∀ (S : Set ℝ)
    (_ : S = { x : ℝ | Real.cos x ^ 2 + Real.cos (2 * x) ^ 2
                     + Real.cos (3 * x) ^ 2 = 1 }),
    S = { x : ℝ | ∃ m : ℤ,
            x = π / 2 + m * π
          ∨ x = π / 4 + m * π / 2
          ∨ x = π / 6 + m * π / 6
          ∨ x = 5 * π / 6 + m * π / 6 }

theorem disproof : ¬ stmt := by
  intro h
  -- Concrete witness S = the LHS set.
  set S : Set ℝ := { x : ℝ | Real.cos x ^ 2 + Real.cos (2 * x) ^ 2
                            + Real.cos (3 * x) ^ 2 = 1 } with hS_def
  have h₀ : S = { x : ℝ | Real.cos x ^ 2 + Real.cos (2 * x) ^ 2
                         + Real.cos (3 * x) ^ 2 = 1 } := rfl
  have hSrhs := h S h₀
  -- 0 ∈ RHS via third branch m = -1: π/6 + (-1)·π/6 = 0
  have h_zero_in_rhs : (0 : ℝ) ∈
      { x : ℝ | ∃ m : ℤ,
            x = π / 2 + m * π
          ∨ x = π / 4 + m * π / 2
          ∨ x = π / 6 + m * π / 6
          ∨ x = 5 * π / 6 + m * π / 6 } := by
    refine ⟨(-1 : ℤ), ?_⟩
    right; right; left
    push_cast
    ring
  -- 0 ∉ S since cos 0 = 1 and 1^2 · 3 = 3 ≠ 1
  have h_zero_notin_S : (0 : ℝ) ∉ S := by
    intro hmem
    have hcos0 : Real.cos 0 = 1 := Real.cos_zero
    have hcos2 : Real.cos (2 * 0) = 1 := by rw [mul_zero]; exact Real.cos_zero
    have hcos3 : Real.cos (3 * 0) = 1 := by rw [mul_zero]; exact Real.cos_zero
    rw [hS_def, Set.mem_setOf_eq, hcos0, hcos2, hcos3] at hmem
    norm_num at hmem
  -- Push the membership through hSrhs.
  rw [hSrhs] at h_zero_notin_S
  exact h_zero_notin_S h_zero_in_rhs

end Minif2fErrata.Imo1962P4

#print axioms Minif2fErrata.Imo1962P4.disproof
