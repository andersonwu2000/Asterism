import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs
import Problems.Minif2f.amc12b_2021_p21.proofs.L_log_strict_gt_on_sqrt2_three

namespace Problems.Minif2f.amc12b_2021_p21

-- Reduce `√2^(2^y) < y^(2^√2)` to its log-linear form
-- `(2^y) · log(√2) < (2^√2) · log y`. Both sides of the original strict
-- inequality are positive (rpow of positive bases), so `Real.log_lt_log_iff`
-- and `Real.log_rpow` give an equivalence; the log form removes nested rpow
-- and exposes the analytical core (concave g(y) := (2^√2)·log y − 2^y·log√2
-- with g(√2)=0 and g(3)>0) for the sub-goal to handle.
theorem s9771 :
    ∀ y : ℝ, 0 < y → Real.sqrt 2 < y → y ≤ 3 →
      Real.sqrt 2 ^ (2:ℝ) ^ y < y ^ (2:ℝ) ^ Real.sqrt 2  := by
  intro y hy_pos hy_lo hy_hi
  have h_log : (2:ℝ) ^ y * Real.log (Real.sqrt 2) <
      (2:ℝ) ^ Real.sqrt 2 * Real.log y :=
    log_strict_gt_on_sqrt2_three y hy_pos hy_lo hy_hi
  have hsqrt2_pos : (0:ℝ) < Real.sqrt 2 := Real.sqrt_pos.mpr (by norm_num)
  have h_lhs_pos : (0:ℝ) < Real.sqrt 2 ^ (2:ℝ) ^ y :=
    Real.rpow_pos_of_pos hsqrt2_pos _
  have h_rhs_pos : (0:ℝ) < y ^ (2:ℝ) ^ Real.sqrt 2 :=
    Real.rpow_pos_of_pos hy_pos _
  rw [← Real.log_lt_log_iff h_lhs_pos h_rhs_pos,
      Real.log_rpow hsqrt2_pos, Real.log_rpow hy_pos]
  exact h_log

end Problems.Minif2f.amc12b_2021_p21
