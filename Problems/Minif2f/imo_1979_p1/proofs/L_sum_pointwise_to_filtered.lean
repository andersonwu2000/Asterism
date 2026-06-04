import Mathlib
import Problems.Minif2f.imo_1979_p1.Defs

namespace Problems.Minif2f.imo_1979_p1

-- sum_pointwise_to_filtered: linearity-of-∑ + sum_filter collapses the if-indicator into the
-- even-filtered sum; Finset.sum_sub_distrib splits the pointwise difference, then ← mul_sum
-- and ← sum_filter reassemble 2*(∑ over filter Even) from ∑ k, 2*(if Even k then 1/k else 0).
theorem sum_pointwise_to_filtered :
    (∑ k ∈ Finset.Icc (1 : ℕ) 1319,
        (((1 : ℝ) / (k : ℝ)) - 2 * (if Even k then ((1 : ℝ) / (k : ℝ)) else 0))) =
      (∑ k ∈ Finset.Icc (1 : ℕ) 1319, ((1 : ℝ) / (k : ℝ))) -
        (2 : ℝ) * (∑ k ∈ (Finset.Icc (1 : ℕ) 1319).filter (fun k => Even k),
                     ((1 : ℝ) / (k : ℝ))) := by
  simp only [Finset.sum_sub_distrib, ← Finset.mul_sum, ← Finset.sum_filter]

end Problems.Minif2f.imo_1979_p1
