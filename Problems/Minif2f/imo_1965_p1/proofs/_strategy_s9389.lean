import Mathlib
import Problems.Minif2f.imo_1965_p1.Defs
import Problems.Minif2f.imo_1965_p1.proofs.L_abs_diff_eq_two_sin_x
import Problems.Minif2f.imo_1965_p1.proofs.L_two_sin_lt_two_cos_low

open BigOperators Real Nat Topology Rat

namespace Problems.Minif2f.imo_1965_p1

-- Lower-bound π/4 ≤ x by contradiction: assume x < π/4 on [0, 2π) and derive 2·cos x < 2·cos x.
-- Sub-goal 1 collapses |√(1+sin 2x) − √(1-sin 2x)| to 2·sin x on [0, π/4).
-- Sub-goal 2 supplies the strict comparison 2·sin x < 2·cos x on the same interval.
-- Combinator: rewrite the absolute value in h₂ via sub-goal 1, then linarith against sub-goal 2.
theorem s9389 : ∀ (x : ℝ) (h₀ : 0 ≤ x) (h₁ : x ≤ 2 * π) (h₂ : 2 * Real.cos x ≤ abs (Real.sqrt (1 + Real.sin (2 * x)) - Real.sqrt (1 - Real.sin (2 * x)))) (h₃ : abs (Real.sqrt (1 + Real.sin (2 * x)) - Real.sqrt (1 - Real.sin (2 * x))) ≤ Real.sqrt 2), π / 4 ≤ x  := by
  intro x h₀ h₁ h₂ h₃
  by_contra hlt
  push_neg at hlt
  have h_eq := abs_diff_eq_two_sin_x x h₀ h₁ h₂ h₃ hlt
  have h_cmp := two_sin_lt_two_cos_low x h₀ h₁ h₂ h₃ hlt
  rw [h_eq] at h₂
  linarith
