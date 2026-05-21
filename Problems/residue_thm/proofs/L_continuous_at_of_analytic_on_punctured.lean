import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
-- continuous_at_of_analytic_on_punctured: AnalyticOn on open punctured set gives ContinuousAt
theorem continuous_at_of_analytic_on_punctured
    {Q : ℂ → ℂ} {a : ℂ}
    (hQ_an : AnalyticOn ℂ Q (Set.univ \ {a}))
    (z : ℂ) (hz : z ∈ Set.univ \ ({a} : Set ℂ)) :
    ContinuousAt Q z := by
  have hopen : IsOpen (Set.univ \ ({a} : Set ℂ)) := isOpen_univ.sdiff isClosed_singleton
  exact hQ_an.continuousOn.continuousAt (hopen.mem_nhds hz)
end Problems.residue_thm
