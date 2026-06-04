import Mathlib
namespace Problems.Minif2f.amc12b_2021_p21

-- six_twentyfifth_le_log_sq_half: lower-bound 6/25 ≤ (log 2)²/2 via Real.log_two_gt_d9 + nlinarith
-- Real.log_two_gt_d9 gives log 2 > 0.6931471803; nlinarith closes with sq_nonneg hint.
theorem six_twentyfifth_le_log_sq_half : (6:ℝ)/25 ≤ (Real.log 2)^2 / 2 := by
  have h := Real.log_two_gt_d9
  nlinarith [sq_nonneg (Real.log 2 - 0.6931471803)]

end Problems.Minif2f.amc12b_2021_p21
