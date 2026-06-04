import Mathlib
import Problems.Minif2f.aime_1994_p4.Defs
import Problems.Minif2f.aime_1994_p4.proofs.L_sum_gt_of_gt_312
import Problems.Minif2f.aime_1994_p4.proofs.L_sum_lt_of_lt_312

namespace Problems.Minif2f.aime_1994_p4

-- Trichotomy on `n` versus `312`: split into `n < 312`, `n = 312`, `n > 312`.
-- Backward sub-goals bound the floor-log sum strictly below/above 1994 on the
-- two strict branches; combined with `hsum : sum = 1994`, both lead to omega
-- contradictions, so only the equality branch survives.
theorem s9275 : ∀ (n : ℕ) (h₀ : 0 < n) (h₀ : (∑ k ∈ Finset.Icc 1 n, Int.floor (Real.logb 2 k)) = 1994), n = 312  := by
  intro n hn hsum
  rcases lt_trichotomy n 312 with hlt | heq | hgt
  · have h_sum_lt := sum_lt_of_lt_312 n hn hlt
    omega
  · exact heq
  · have h_sum_gt := sum_gt_of_gt_312 n hgt
    omega

end Problems.Minif2f.aime_1994_p4
