import Mathlib
import Problems.Minif2f.amc12a_2010_p22.Defs
import Problems.Minif2f.amc12a_2010_p22.proofs.L_sum_neg_le_sum_abs
import Problems.Minif2f.amc12a_2010_p22.proofs.L_sum_one_minus_kx_value

namespace Problems.Minif2f.amc12a_2010_p22

-- Pointwise bound `1 - k*x ≤ |k*x - 1|` summed over Icc 1 84, plus a closed-form
-- evaluation of `∑ (1 - k*x) = 84 - 3570*x`. Linarith chains the two.
theorem s9460 (x : ℝ) :
    (84:ℝ) - 3570 * x ≤ ∑ k ∈ (Finset.Icc (1:ℤ) 84), abs ((k:ℝ) * x - 1)  := by
  have h_sum_bound := sum_neg_le_sum_abs x
  have h_sum_value := sum_one_minus_kx_value x
  linarith [h_sum_bound, h_sum_value]

end Problems.Minif2f.amc12a_2010_p22
