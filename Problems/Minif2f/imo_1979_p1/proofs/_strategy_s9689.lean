import Mathlib
import Problems.Minif2f.imo_1979_p1.Defs
import Problems.Minif2f.imo_1979_p1.proofs.L_alt_split_filter_even
import Problems.Minif2f.imo_1979_p1.proofs.L_filter_even_eq_double_image

namespace Problems.Minif2f.imo_1979_p1

-- Bridge alternating sum to (full − 2·even-half) by splitting the sign and reindexing.
-- h_alt_split: rewrite ∑ (-1)^(k+1)/k as ∑ 1/k − 2·∑_{Even k} 1/k via term-wise sign manipulation.
-- h_filter_reindex: identify the even-filtered sum with the j ↦ 2j reindexing onto [1,659].
theorem s9689 :
    (∑ k ∈ Finset.Icc (1 : ℕ) 1319, (-1 : ℝ) ^ (k + 1) * ((1 : ℝ) / (k : ℝ))) =
      (∑ k ∈ Finset.Icc (1 : ℕ) 1319, ((1 : ℝ) / (k : ℝ))) -
        (2 : ℝ) * (∑ j ∈ Finset.Icc (1 : ℕ) 659, ((1 : ℝ) / ((2 * j : ℕ) : ℝ)))  := by
  have h_alt_split := alt_split_filter_even
  have h_filter_reindex := filter_even_eq_double_image
  rw [h_filter_reindex] at h_alt_split
  exact h_alt_split

end Problems.Minif2f.imo_1979_p1
