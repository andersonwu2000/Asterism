import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs
import Problems.Minif2f.amc12b_2021_p21.proofs.L_cube_lt_dbl_exp_scaled
import Problems.Minif2f.amc12b_2021_p21.proofs.L_six_twentyfifth_le_log_sq_half

namespace Problems.Minif2f.amc12b_2021_p21

-- Split the strict bound into the analytic cube-vs-scaled-double-exp content
-- (`25 * t^3 < 6 * √2^(2^t + 2t)` for t > 3) and a rational lower bound
-- `6/25 ≤ (log 2)^2 / 2` (numerically tight, provable from `Real.log_two_gt_d9`).
-- Combine multiplicatively: `t^3 < (6/25) * √2^…  ≤  (log 2)^2/2 * √2^…`,
-- using positivity of `√2^…` to scale the rational bound.
theorem s9832 : ∀ t : ℝ, 3 < t →
    t ^ 3 < (Real.log 2)^2 / 2 * Real.sqrt 2 ^ ((2 : ℝ) ^ t + 2 * t)  := by
  intro t ht
  have hA := cube_lt_dbl_exp_scaled t ht
  have hB := six_twentyfifth_le_log_sq_half
  have hX_pos : (0:ℝ) < Real.sqrt 2 ^ ((2:ℝ) ^ t + 2*t) :=
    Real.rpow_pos_of_pos (Real.sqrt_pos.mpr (by norm_num)) _
  have step1 : t^3 < 6/25 * Real.sqrt 2 ^ ((2:ℝ) ^ t + 2*t) := by linarith
  have step2 : (6:ℝ)/25 * Real.sqrt 2 ^ ((2:ℝ) ^ t + 2*t) ≤
      (Real.log 2)^2/2 * Real.sqrt 2 ^ ((2:ℝ) ^ t + 2*t) :=
    mul_le_mul_of_nonneg_right hB hX_pos.le
  linarith

end Problems.Minif2f.amc12b_2021_p21
