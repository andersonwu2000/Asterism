import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs
import Problems.Minif2f.amc12b_2021_p21.proofs.L_log_form_cube_four_pow

namespace Problems.Minif2f.amc12b_2021_p21

-- Sandwich via log monotonicity: positivity of both sides + log-inequality
-- `log 25 + 3 log t < log 12 + t log 4` collapse to the original via
-- `Real.log_lt_log_iff`, `Real.log_mul`, `Real.log_pow`, `Real.log_rpow`.
-- Sub-goal `log_form_cube_four_pow` carries the single analytic core.
theorem s9840 :
    ∀ t : ℝ, 3 < t → 25 * t^3 < 12 * (4:ℝ)^t  := by
  intro t ht
  have ht_pos : (0:ℝ) < t := by linarith
  have hlhs_pos : (0:ℝ) < 25 * t^3 := by positivity
  have hrhs_pos : (0:ℝ) < 12 * (4:ℝ)^t := by positivity
  have h_log_ineq : Real.log 25 + 3 * Real.log t
      < Real.log 12 + t * Real.log 4 := log_form_cube_four_pow t ht
  rw [← Real.log_lt_log_iff hlhs_pos hrhs_pos]
  rw [Real.log_mul (by norm_num : (25:ℝ) ≠ 0) (by positivity : t^3 ≠ 0)]
  rw [Real.log_mul (by norm_num : (12:ℝ) ≠ 0)
      (Real.rpow_pos_of_pos (by norm_num : (0:ℝ) < 4) t).ne']
  rw [Real.log_pow, Real.log_rpow (by norm_num : (0:ℝ) < 4)]
  push_cast
  linarith

end Problems.Minif2f.amc12b_2021_p21
