import Mathlib
import Problems.Minif2f.amc12a_2010_p22.Defs
import Problems.Minif2f.amc12a_2010_p22.proofs.L_sum_lower_half_bound
import Problems.Minif2f.amc12a_2010_p22.proofs.L_sum_split_at_84
import Problems.Minif2f.amc12a_2010_p22.proofs.L_sum_upper_half_bound

namespace Problems.Minif2f.amc12a_2010_p22

-- Triangle-inequality split of the sum ∑_{k=1}^{119} |kx - 1| at k = 84/85.
-- Sub-goals: (1) a Finset split identity at 84, (2) lower-half bound
--   ∑_{k=1}^{84} |kx-1| ≥ 84 - 3570x  (by |·| ≥ -·, and ∑_{k=1}^{84} k = 3570),
-- (3) upper-half bound ∑_{k=85}^{119} |kx-1| ≥ 3570x - 35
--   (by |·| ≥ ·, and ∑_{k=85}^{119} k = 3570 with 35 terms).
-- Summing gives (84 - 3570x) + (3570x - 35) = 49, closed by `rw [h_split]; linarith`.
theorem s9354 : ∀ (x : ℝ), 49 ≤ ∑ k ∈ (Finset.Icc (1:ℤ) (119:ℤ)), abs (k * x - 1)  := by
  intro x
  have h_split := sum_split_at_84 x
  have h_lower := sum_lower_half_bound x
  have h_upper := sum_upper_half_bound x
  rw [h_split]
  linarith

end Problems.Minif2f.amc12a_2010_p22
