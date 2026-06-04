import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs

namespace Problems.Minif2f.amc12b_2021_p21

-- log_form_cube_four_pow: log 25 + 3*log t < log 12 + t*log 4 for t > 3,
-- via log t ≤ log 3 + (t/3 - 1) (tangent-line bound) + log(64/27) > log(25/12)
theorem log_form_cube_four_pow :
    ∀ t : ℝ, 3 < t → Real.log 25 + 3 * Real.log t
      < Real.log 12 + t * Real.log 4 := by
  intro t ht
  have ht0 : (0 : ℝ) < t := by linarith
  have h_log_bound : Real.log t ≤ Real.log 3 + (t / 3 - 1) := by
    have h_t3 : (0 : ℝ) < t / 3 := by positivity
    have h1 : t / 3 ≤ Real.exp (t / 3 - 1) := by
      linarith [Real.add_one_le_exp (t / 3 - 1)]
    have h2 : Real.log (t / 3) ≤ t / 3 - 1 :=
      calc Real.log (t / 3) ≤ Real.log (Real.exp (t / 3 - 1)) :=
            Real.log_le_log h_t3 h1
          _ = t / 3 - 1 := Real.log_exp _
    have h3 : Real.log t = Real.log 3 + Real.log (t / 3) := by
      rw [← Real.log_mul (by norm_num : (3:ℝ) ≠ 0) h_t3.ne']
      congr 1; ring
    linarith
  have h_log4_gt_1 : 1 < Real.log 4 := by
    rw [show (1:ℝ) = Real.log (Real.exp 1) from (Real.log_exp 1).symm]
    apply Real.log_lt_log (Real.exp_pos 1)
    exact lt_trans Real.exp_one_lt_d9 (by norm_num)
  have h_key : Real.log 25 - Real.log 12 < 3 * (Real.log 4 - Real.log 3) := by
    have h4 : (3:ℝ) * Real.log 4 = Real.log 64 := by
      rw [show (64:ℝ) = 4^3 from by norm_num, Real.log_pow]; push_cast; ring
    have h3 : (3:ℝ) * Real.log 3 = Real.log 27 := by
      rw [show (27:ℝ) = 3^3 from by norm_num, Real.log_pow]; push_cast; ring
    have h_lt : Real.log (25/12 : ℝ) < Real.log (64/27 : ℝ) :=
      Real.log_lt_log (by norm_num) (by norm_num)
    calc Real.log 25 - Real.log 12
        = Real.log (25/12) := (Real.log_div (by norm_num) (by norm_num)).symm
      _ < Real.log (64/27) := h_lt
      _ = Real.log 64 - Real.log 27 := Real.log_div (by norm_num) (by norm_num)
      _ = 3 * Real.log 4 - 3 * Real.log 3 := by rw [← h4, ← h3]
      _ = 3 * (Real.log 4 - Real.log 3) := by ring
  have h3 : 3 * Real.log t ≤ 3 * Real.log 3 + (t - 3) := by linarith
  have h_mul : (0:ℝ) < (Real.log 4 - 1) * (t - 3) :=
    mul_pos (by linarith) (by linarith)
  nlinarith [h3, h_key, h_mul]

end Problems.Minif2f.amc12b_2021_p21
