import Mathlib
import Problems.Minif2f.aime_1997_p11.Defs
import Problems.Minif2f.aime_1997_p11.proofs.L_sum_cos_eq_sum_sin_scaled
import Problems.Minif2f.aime_1997_p11.proofs.L_sum_sin_ne_zero

open BigOperators Real Nat Topology Rat

namespace Problems.Minif2f.aime_1997_p11

-- Closed-form: pair-and-shift identity gives Σ cos = (1+√2)·Σ sin, and Σ sin > 0 lets us divide.
-- (1) sum_cos_eq_sum_sin_scaled: numerator equals (1+√2) times denominator.
-- (2) sum_sin_ne_zero: denominator is non-zero (positive sum of sines of acute angles).
set_option linter.style.longLine false in
theorem s758 : ∀ (x : ℝ) (_h₀ : x = (∑ n ∈ Finset.Icc (1 : ℕ) 44, Real.cos (n * π / 180)) / ∑ n ∈ Finset.Icc (1 : ℕ) 44, Real.sin (n * π / 180)), x = 1 + Real.sqrt 2  := by
  intro x h₀
  have h_sum_cos_eq : (∑ n ∈ Finset.Icc (1 : ℕ) 44, Real.cos (n * π / 180)) =
      (1 + Real.sqrt 2) * (∑ n ∈ Finset.Icc (1 : ℕ) 44, Real.sin (n * π / 180)) :=
    sum_cos_eq_sum_sin_scaled
  have h_sum_sin_ne_zero :
      (∑ n ∈ Finset.Icc (1 : ℕ) 44, Real.sin (n * π / 180)) ≠ 0 :=
    sum_sin_ne_zero
  rw [h₀, h_sum_cos_eq, mul_div_assoc, div_self h_sum_sin_ne_zero, mul_one]

end Problems.Minif2f.aime_1997_p11
