import Mathlib
namespace Problems.Minif2f.amc12b_2021_p21

-- pow_sqrt2_lower: bound 2^√2 ≥ 13/5 via 5th-power comparison: (13/5)^5 ≤ 2^7,
-- lifted through rpow by taking (·)^(1/5), chained with 2^(7/5) ≤ 2^√2 via √2 ≥ 7/5.
theorem pow_sqrt2_lower :
    (13:ℝ)/5 ≤ (2:ℝ)^Real.sqrt 2 := by
  have hsqrt : (7:ℝ)/5 ≤ Real.sqrt 2 := by
    rw [Real.le_sqrt (by norm_num : (0:ℝ) ≤ 7/5) (by norm_num : (0:ℝ) ≤ 2)]
    norm_num
  have hmid : (13:ℝ)/5 ≤ (2:ℝ)^((7:ℝ)/5) := by
    have heq : ((2:ℝ)^((7:ℝ)/5))^(5:ℕ) = 2^(7:ℕ) := by
      rw [← Real.rpow_natCast ((2:ℝ)^((7:ℝ)/5)) 5]
      rw [← Real.rpow_mul (by norm_num : (0:ℝ) ≤ 2)]
      norm_num
    have h5 : ((13:ℝ)/5)^(5:ℕ) ≤ ((2:ℝ)^((7:ℝ)/5))^(5:ℕ) := by
      rw [heq]; norm_num
    have step := Real.rpow_le_rpow (by positivity : (0:ℝ) ≤ ((13:ℝ)/5)^5)
      (show ((13:ℝ)/5)^(5:ℕ) ≤ ((2:ℝ)^((7:ℝ)/5))^(5:ℕ) from h5)
      (by norm_num : (0:ℝ) ≤ 1/5)
    have lhs : (((13:ℝ)/5)^(5:ℕ))^((1:ℝ)/5) = 13/5 := by
      rw [← Real.rpow_natCast ((13:ℝ)/5) 5, ← Real.rpow_mul (by norm_num)]
      norm_num
    have rhs : (((2:ℝ)^((7:ℝ)/5))^(5:ℕ))^((1:ℝ)/5) = (2:ℝ)^((7:ℝ)/5) := by
      rw [← Real.rpow_natCast ((2:ℝ)^((7:ℝ)/5)) 5, ← Real.rpow_mul (by positivity)]
      norm_num
    rw [lhs, rhs] at step
    exact step
  calc (13:ℝ)/5 ≤ (2:ℝ)^((7:ℝ)/5) := hmid
    _ ≤ (2:ℝ)^Real.sqrt 2 := Real.rpow_le_rpow_of_exponent_le (by norm_num) hsqrt

end Problems.Minif2f.amc12b_2021_p21
