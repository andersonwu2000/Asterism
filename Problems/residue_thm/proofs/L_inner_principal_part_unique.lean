import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Backward
theorem inner_principal_part_unique
    {a : ℂ} {Q1 Q2 : ℂ → ℂ} {R : ℝ} {g : ℂ → ℂ}
    (hR : 0 < R)
    (hQ1 : AnalyticOn ℂ Q1 (Set.univ \ {a}))
    (hQ1_tendsto : Filter.Tendsto Q1 (Filter.cocompact ℂ) (nhds 0))
    (hQ2 : AnalyticOn ℂ Q2 (Set.univ \ {a}))
    (hQ2_tendsto : Filter.Tendsto Q2 (Filter.cocompact ℂ) (nhds 0))
    (hg : AnalyticOn ℂ g (Metric.ball a R))
    (h_diff_eq : ∀ w ∈ Metric.ball a R \ {a}, Q1 w - Q2 w = g w) :
    ∀ w, w ≠ a → Q1 w = Q2 w := by sorry

end Problems.residue_thm
