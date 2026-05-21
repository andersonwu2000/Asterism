import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
theorem continuous_on_punctured_of_analytic
    {Q : ℂ → ℂ} {a : ℂ}
    (hQ_an : AnalyticOn ℂ Q (Set.univ \ {a})) :
    ContinuousOn Q (Set.univ \ ({a} : Set ℂ)) := by exact AnalyticOn.continuousOn hQ_an

end Problems.residue_thm
