import Mathlib
import Problems.Minif2f.imo_1979_p1.Defs
import Problems.Minif2f.imo_1979_p1.proofs.L_pointwise_sign_to_diff
import Problems.Minif2f.imo_1979_p1.proofs.L_sum_pointwise_to_filtered

namespace Problems.Minif2f.imo_1979_p1

-- Bridge alternating sum to (full − 2·even-half) via two strictly simpler pieces:
-- `pointwise_sign_to_diff`: the ∀-quantified termwise identity
--   (-1)^(k+1)·(1/k) = 1/k − 2·(if Even k then 1/k else 0)
-- `sum_pointwise_to_filtered`: linearity-of-∑ + Finset.sum_filter to collapse
--   the indicator-weighted sum into a sum over the Even-filtered Icc.
-- Combine: rewrite the alternating sum termwise, then invoke the assembly.
theorem s9750 :
    (∑ k ∈ Finset.Icc (1 : ℕ) 1319, (-1 : ℝ) ^ (k + 1) * ((1 : ℝ) / (k : ℝ))) =
      (∑ k ∈ Finset.Icc (1 : ℕ) 1319, ((1 : ℝ) / (k : ℝ))) -
        (2 : ℝ) * (∑ k ∈ (Finset.Icc (1 : ℕ) 1319).filter (fun k => Even k),
                     ((1 : ℝ) / (k : ℝ)))  := by
  have h_pointwise := pointwise_sign_to_diff
  have h_assemble := sum_pointwise_to_filtered
  rw [Finset.sum_congr rfl (fun k _ => h_pointwise k)]
  exact h_assemble

end Problems.Minif2f.imo_1979_p1
