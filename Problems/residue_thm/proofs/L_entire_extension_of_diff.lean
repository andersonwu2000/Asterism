import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Backward
theorem entire_extension_of_diff
    {a : ℂ} {Q1 Q2 : ℂ → ℂ} {R : ℝ} {g : ℂ → ℂ}
    (hR : 0 < R)
    (hQ1 : AnalyticOn ℂ Q1 (Set.univ \ {a}))
    (hQ2 : AnalyticOn ℂ Q2 (Set.univ \ {a}))
    (hg : AnalyticOn ℂ g (Metric.ball a R))
    (h_diff_eq : ∀ w ∈ Metric.ball a R \ {a}, Q1 w - Q2 w = g w) :
    ∃ h_ext : ℂ → ℂ, AnalyticOn ℂ h_ext Set.univ ∧
      (∀ w, w ≠ a → h_ext w = Q1 w - Q2 w) := by sorry

end Problems.residue_thm
