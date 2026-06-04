import Mathlib
namespace Problems.Minif2f.amc12b_2021_p21

-- lhs_simp_g_three: simplify 2^3 * log(√2) to 4*log 2 via sqrt_eq_rpow + log_rpow + ring
theorem lhs_simp_g_three :
    (2:ℝ)^(3:ℝ) * Real.log (Real.sqrt 2) = 4 * Real.log 2 := by
  rw [Real.sqrt_eq_rpow, Real.log_rpow (by norm_num : (0:ℝ) < 2)]
  norm_num [Real.rpow_natCast]; ring

end Problems.Minif2f.amc12b_2021_p21
