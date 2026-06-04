import Mathlib
namespace Problems.Minif2f.amc12b_2021_p21

-- func_diff_four_nonpos: rpow monotonicity + sqrt 2 ≤ 2 closes 4^(2^√2) ≤ √2^16
-- Both sides equal 256 = 4^4; LHS ≤ 4^4 since 2^√2 ≤ 4 (from √2 ≤ 2);
-- RHS = √2^16 = (2^(1/2))^16 = 2^8 = 4^4 by rpow_mul.
theorem func_diff_four_nonpos :
    (4:ℝ)^((2:ℝ)^Real.sqrt 2) - Real.sqrt 2 ^ ((2:ℝ)^(4:ℝ)) ≤ 0 := by
  rw [sub_nonpos]
  have hsqrt2_le : Real.sqrt 2 ≤ 2 := by
    have : Real.sqrt 2 * Real.sqrt 2 = 2 := Real.mul_self_sqrt (by norm_num)
    nlinarith [Real.sqrt_nonneg 2]
  have hexp_le : (2:ℝ)^Real.sqrt 2 ≤ 4 := by
    have h1 : (2:ℝ)^Real.sqrt 2 ≤ (2:ℝ)^(2:ℝ) :=
      Real.rpow_le_rpow_of_exponent_le (by norm_num) hsqrt2_le
    have h2 : (2:ℝ)^(2:ℝ) = 4 := by norm_num
    linarith
  have hlhs : (4:ℝ)^((2:ℝ)^Real.sqrt 2) ≤ (4:ℝ)^(4:ℝ) :=
    Real.rpow_le_rpow_of_exponent_le (by norm_num) hexp_le
  have hrhs : Real.sqrt 2 ^ ((2:ℝ)^(4:ℝ)) = (4:ℝ)^(4:ℝ) := by
    have h16 : (2:ℝ)^(4:ℝ) = 16 := by norm_num
    rw [h16, Real.sqrt_eq_rpow, ← Real.rpow_mul (by norm_num : (0:ℝ) ≤ 2)]
    norm_num
  linarith

end Problems.Minif2f.amc12b_2021_p21
