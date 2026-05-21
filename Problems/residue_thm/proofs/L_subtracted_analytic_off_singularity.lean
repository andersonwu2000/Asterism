import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- subtracted_analytic_off_singularity: analyticity of P z - residue P a / (z - a) on ℂ \ {a}.
-- Uses hP.sub + AnalyticOn.div (const, id - const) with denominator nonzero on ℂ \ {a}.
-- entry_kind: Builder
theorem subtracted_analytic_off_singularity
    {P : ℂ → ℂ} {a : ℂ}
    (hP : AnalyticOn ℂ P (Set.univ \ {a})) :
    AnalyticOn ℂ (fun z => P z - Complex.residue P a / (z - a))
      (Set.univ \ {a}) := by
  apply hP.sub
  apply AnalyticOn.div analyticOn_const (analyticOn_id.sub analyticOn_const)
  intro z hz
  simp only [Set.mem_diff, Set.mem_univ, Set.mem_singleton_iff, true_and] at hz
  exact sub_ne_zero.mpr hz

end Problems.residue_thm

