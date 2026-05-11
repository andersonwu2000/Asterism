/-
  Sandbox disproof of the minif2f-transcribed statement of `aime_1988_p3`.

  ## Background
  Statement (as imported):
    ∀ (x : ℝ) (h₀ : 0 < x)
      (h₁ : Real.logb 2 (Real.logb 8 x) = Real.logb 8 (Real.logb 2 x)),
      Real.logb 2 x ^ 2 = 27

  ## Bug
  The original AIME 1988 #3 implicitly assumes `x > 1` so that `log₂ x > 0`
  and `log₈ x > 0`, making the inner logarithms well-defined as positive
  reals. The Lean statement only assumes `0 < x`, admitting `x = 1` (and
  any `x` for which one of the inner logs is non-positive) as a
  counterexample under Mathlib's total-log convention (`Real.log 0 = 0`,
  hence `Real.logb b 0 = 0`).

  ## Counterexample: x = 1
    h₀: 0 < 1 ✓
    h₁: Real.logb 2 (Real.logb 8 1) = Real.logb 2 0 = 0
         = Real.logb 8 0 = Real.logb 8 (Real.logb 2 1) ✓
    conclusion: Real.logb 2 1 ^ 2 = 0 ^ 2 = 0 ≠ 27 ✗

  ## How to verify
    cd D:/Asterism
    lake env lean docs/errata/minif2f/aime_1988_p3_disproof.lean
  Expected: clean elaboration; axioms = [propext, Classical.choice, Quot.sound].
-/
import Mathlib

namespace Minif2fErrata.Aime1988P3

def stmt : Prop :=
  ∀ (x : ℝ) (_ : 0 < x)
    (_ : Real.logb 2 (Real.logb 8 x) = Real.logb 8 (Real.logb 2 x)),
    Real.logb 2 x ^ 2 = 27

theorem disproof : ¬ stmt := by
  intro h
  -- Specialize at x = 1
  have h0 : (0 : ℝ) < 1 := by norm_num
  -- Real.logb b 1 = 0 for any b
  have hlog1 : ∀ b : ℝ, Real.logb b 1 = 0 := by
    intro b; simp [Real.logb, Real.log_one]
  -- h₁ : Real.logb 2 (Real.logb 8 1) = Real.logb 8 (Real.logb 2 1)
  -- both inner logs are 0 (logb _ 1 = 0), and Real.logb _ 0 = 0
  have h1 : Real.logb 2 (Real.logb 8 1) = Real.logb 8 (Real.logb 2 1) := by
    rw [hlog1 8, hlog1 2, Real.logb_zero, Real.logb_zero]
  -- Apply h to derive Real.logb 2 1 ^ 2 = 27, but logb 2 1 = 0
  have key := h 1 h0 h1
  rw [hlog1 2] at key
  -- key : (0 : ℝ) ^ 2 = 27
  norm_num at key

end Minif2fErrata.Aime1988P3

#print axioms Minif2fErrata.Aime1988P3.disproof
