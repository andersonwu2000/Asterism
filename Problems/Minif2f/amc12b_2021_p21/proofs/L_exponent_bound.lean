import Mathlib
namespace Problems.Minif2f.amc12b_2021_p21

-- exponent_bound: rpow_le_rpow_of_exponent_le with numeric bound 2^√2 ≤ 3 via √2 ≤ 3/2
-- Since z > 4 ≥ 1, monotonicity in the exponent reduces the goal to 2^√2 ≤ 3.
-- That follows from √2 ≤ 3/2 (since (√2)^2 = 2 ≤ 9/4) and 2^(3/2) = 2√2 ≤ 3.
open Real in
theorem exponent_bound : ∀ z : ℝ, 4 < z → z ^ ((2:ℝ) ^ Real.sqrt 2) ≤ z ^ (3:ℝ) := by
  intro z hz
  apply Real.rpow_le_rpow_of_exponent_le
  · linarith
  · have hsq2_nn : (0:ℝ) ≤ Real.sqrt 2 := Real.sqrt_nonneg 2
    have hsq2_sq : Real.sqrt 2 ^ 2 = 2 := Real.sq_sqrt (by norm_num)
    have hsq2_le : Real.sqrt 2 ≤ 3/2 := by nlinarith [sq_nonneg (Real.sqrt 2 - 3/2)]
    calc (2:ℝ) ^ Real.sqrt 2
        ≤ (2:ℝ) ^ (3/2 : ℝ) :=
          Real.rpow_le_rpow_of_exponent_le (by norm_num) hsq2_le
      _ = 2 * Real.sqrt 2 := by
          rw [show (3/2 : ℝ) = 1 + 1/2 by norm_num]
          rw [Real.rpow_add (by norm_num : (0:ℝ) < 2)]
          rw [Real.rpow_one]
          rw [← Real.sqrt_eq_rpow]
      _ ≤ 3 := by nlinarith [sq_nonneg (Real.sqrt 2 - 3/2)]

end Problems.Minif2f.amc12b_2021_p21
