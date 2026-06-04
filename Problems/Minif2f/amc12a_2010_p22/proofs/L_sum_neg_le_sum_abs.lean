import Mathlib
namespace Problems.Minif2f.amc12a_2010_p22

-- sum_neg_le_sum_abs: lift pointwise `1 - k*x ≤ |k*x - 1|` via Finset.sum_le_sum;
-- pointwise bound follows from `le_abs_self (1 - k*x)` + `abs_sub_comm`.
theorem sum_neg_le_sum_abs (x : ℝ) :
    ∑ k ∈ (Finset.Icc (1:ℤ) 84), (1 - (k:ℝ) * x) ≤
    ∑ k ∈ (Finset.Icc (1:ℤ) 84), abs ((k:ℝ) * x - 1) := by
  apply Finset.sum_le_sum
  intro k _
  have h := le_abs_self (1 - (k:ℝ) * x)
  rwa [abs_sub_comm] at h

end Problems.Minif2f.amc12a_2010_p22
