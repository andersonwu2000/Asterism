import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs

namespace Problems.Minif2f.amc12b_2021_p21

-- four_mul_le_two_pow: 4z ≤ 2^z for z > 4 via splitting exp and linear lower bound
-- Write 2^z = exp(log2 * z) = 16 * exp(log2 * (z-4)); use exp(x) ≥ x+1 and log2 ≥ 1/4.
theorem four_mul_le_two_pow :
    ∀ z : ℝ, 4 < z → 4 * z ≤ (2:ℝ) ^ z := by
  intro z hz
  have h2 : (0:ℝ) < 2 := by norm_num
  rw [Real.rpow_def_of_pos h2]
  have hlog2_lb : (1:ℝ)/4 ≤ Real.log 2 := by
    have := Real.log_two_gt_d9; linarith
  have hlog2_pos : 0 < Real.log 2 := Real.log_pos (by norm_num)
  have h16 : Real.exp (Real.log 2 * 4) = 16 := by
    have hlog : Real.log 2 * 4 = Real.log ((2:ℝ) ^ (4:ℕ)) := by
      rw [Real.log_pow]; push_cast; ring
    rw [hlog, Real.exp_log (by norm_num : (0:ℝ) < (2:ℝ) ^ (4:ℕ))]
    norm_num
  have hexp_split : Real.exp (Real.log 2 * z) = 16 * Real.exp (Real.log 2 * (z - 4)) := by
    rw [show Real.log 2 * z = Real.log 2 * 4 + Real.log 2 * (z - 4) by ring,
        Real.exp_add, h16]
  rw [hexp_split]
  have hineq : (1:ℝ)/4 * (z - 4) ≤ Real.log 2 * (z - 4) :=
    mul_le_mul_of_nonneg_right hlog2_lb (by linarith)
  have hexp_lb : Real.log 2 * (z - 4) + 1 ≤ Real.exp (Real.log 2 * (z - 4)) :=
    Real.add_one_le_exp (Real.log 2 * (z - 4))
  nlinarith [Real.exp_pos (Real.log 2 * (z - 4))]

end Problems.Minif2f.amc12b_2021_p21
