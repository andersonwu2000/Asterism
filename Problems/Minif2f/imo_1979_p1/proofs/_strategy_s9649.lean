import Mathlib
import Problems.Minif2f.imo_1979_p1.Defs
import Problems.Minif2f.imo_1979_p1.proofs.L_alt_eq_full_minus_double_even
import Problems.Minif2f.imo_1979_p1.proofs.L_two_mul_recip_two_j_eq_recip_j

namespace Problems.Minif2f.imo_1979_p1

-- Bridge alternating sum to (sum_all − sum_head) via the even-indexed half.
-- h_alt rewrites the alternating sum as full minus 2·(sum of 1/(2j) for j∈[1,659]);
-- h_double collapses 2·∑ 1/(2j) to ∑ 1/j. Combine with linarith.
theorem s9649 :
    (∑ k ∈ Finset.Icc (1 : ℕ) 1319, (-1 : ℝ) ^ (k + 1) * ((1 : ℝ) / (k : ℝ))) =
      (∑ k ∈ Finset.Icc (1 : ℕ) 1319, ((1 : ℝ) / (k : ℝ))) -
        (∑ j ∈ Finset.Icc (1 : ℕ) 659, ((1 : ℝ) / (j : ℝ)))  := by
  have h_alt := alt_eq_full_minus_double_even
  have h_double := two_mul_recip_two_j_eq_recip_j
  linarith [h_alt, h_double]

end Problems.Minif2f.imo_1979_p1
