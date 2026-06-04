import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs

namespace Problems.Minif2f.amc12b_2021_p21

-- poly_lt_four_pow: log comparison via Real.add_one_le_exp bound and Real.exp_one_lt_d9
-- Chain: 3*log(z) ≤ 3*log(4) + 3z/4 - 3 < z*log(4) using log(z/4) ≤ z/4-1 and log(4) > 1.
theorem poly_lt_four_pow : ∀ z : ℝ, 4 < z → z ^ (3:ℝ) < (4:ℝ) ^ z := by
  intro z hz
  have hz0 : (0:ℝ) < z := by linarith
  have h40 : (0:ℝ) < (4:ℝ) := by norm_num
  rw [← Real.log_lt_log_iff (Real.rpow_pos_of_pos hz0 3) (Real.rpow_pos_of_pos h40 z)]
  rw [Real.log_rpow hz0, Real.log_rpow h40]
  have hlog_div : Real.log (z / 4) ≤ z / 4 - 1 := by
    have h1 : z / 4 - 1 + 1 ≤ Real.exp (z / 4 - 1) := Real.add_one_le_exp _
    have hz4_pos : (0:ℝ) < z / 4 := by linarith
    have h2 : z / 4 ≤ Real.exp (z / 4 - 1) := by linarith
    have h3 : Real.log (z / 4) ≤ Real.log (Real.exp (z / 4 - 1)) :=
      Real.log_le_log hz4_pos h2
    rwa [Real.log_exp] at h3
  have hlog_z : 3 * Real.log z ≤ 3 * Real.log 4 + 3 * z / 4 - 3 := by
    have hlog_split : Real.log z = Real.log 4 + Real.log (z / 4) := by
      rw [Real.log_div (ne_of_gt hz0) (ne_of_gt h40)]
      ring
    linarith [hlog_split]
  have hlog4_gt1 : (1:ℝ) < Real.log 4 := by
    rw [show (1:ℝ) = Real.log (Real.exp 1) from (Real.log_exp 1).symm]
    apply Real.log_lt_log (Real.exp_pos 1)
    exact lt_trans Real.exp_one_lt_d9 (by norm_num)
  have hstep4 : 3 * Real.log 4 + 3 * z / 4 - 3 < z * Real.log 4 := by
    have hlog4_pos : (0:ℝ) < Real.log 4 := by linarith
    nlinarith
  linarith

end Problems.Minif2f.amc12b_2021_p21
