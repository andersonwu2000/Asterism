import Mathlib
import Problems.Minif2f.aime_1997_p11.Defs
import Problems.Minif2f.aime_1997_p11.proofs.L_cos_sum_eq_one_plus_sqrt_two_mul_sin_sum
import Problems.Minif2f.aime_1997_p11.proofs.L_sin_sum_pos_ne_zero

open BigOperators Real Nat Topology Rat

namespace Problems.Minif2f.aime_1997_p11

-- Reduce x = (Σcos)/(Σsin) = 1+√2 by clearing the denominator.
-- (1) cos_sum_eq_one_plus_sqrt_two_mul_sin_sum: numerator equals (1+√2)·denominator.
-- (2) sin_sum_pos_ne_zero: denominator is non-zero (positive sum of sines of acute angles).
set_option linter.style.longLine false in
theorem s9641 : ∀ (x : ℝ) (_h₀ : x = (∑ n ∈ Finset.Icc (1 : ℕ) 44, Real.cos (n * π / 180)) / ∑ n ∈ Finset.Icc (1 : ℕ) 44, Real.sin (n * π / 180)), x = 1 + Real.sqrt 2  := by
  intro x h₀
  have h_scaled : (∑ n ∈ Finset.Icc (1 : ℕ) 44, Real.cos (n * π / 180)) =
      (1 + Real.sqrt 2) * (∑ n ∈ Finset.Icc (1 : ℕ) 44, Real.sin (n * π / 180)) :=
    cos_sum_eq_one_plus_sqrt_two_mul_sin_sum
  have h_ne : (∑ n ∈ Finset.Icc (1 : ℕ) 44, Real.sin (n * π / 180)) ≠ 0 :=
    sin_sum_pos_ne_zero
  rw [h₀, h_scaled, mul_div_assoc, div_self h_ne, mul_one]

end Problems.Minif2f.aime_1997_p11
