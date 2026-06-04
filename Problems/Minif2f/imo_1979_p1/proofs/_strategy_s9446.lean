import Mathlib
import Problems.Minif2f.imo_1979_p1.Defs
import Problems.Minif2f.imo_1979_p1.proofs.L_alt_eq_tail
import Problems.Minif2f.imo_1979_p1.proofs.L_tail_eq_pair_sum

namespace Problems.Minif2f.imo_1979_p1

-- IMO 1979 P1 pairing trick: rewrite alternating sum into 1979 × pair-sum.
-- (1) `alt_eq_tail`: alternating sum = tail sum ∑_{k=660}^{1319} 1/k
-- (2) `tail_eq_pair_sum`: tail sum = 1979 × ∑_{j<330} 1/((660+j)(1319-j))
-- Combine by transitivity.
theorem s9446 :
    (∑ k ∈ Finset.Icc (1 : ℕ) 1319, (-1) ^ (k + 1) * ((1 : ℝ) / k)) =
      (1979 : ℝ) *
        ∑ j ∈ Finset.range 330,
          (1 : ℝ) / ((660 + (j : ℝ)) * (1319 - (j : ℝ)))  := by
  have h1 := alt_eq_tail
  have h2 := tail_eq_pair_sum
  exact h1.trans h2

end Problems.Minif2f.imo_1979_p1
