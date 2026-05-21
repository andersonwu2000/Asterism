import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_param_int_continuous_at_of_joint

namespace Problems.residue_thm

-- Localize: ContinuousOn on the open set U reduces to ContinuousAt at every
-- point w₀ ∈ U. The single sub-goal `param_int_continuous_at_of_joint`
-- furnishes the pointwise continuity; assembly is `ContinuousAt.continuousWithinAt`.
theorem s10636
    {U : Set ℂ} {a b : ℝ} {F : ℂ → ℝ → ℂ}
    (hU : IsOpen U)
    (hF : ContinuousOn (fun p : ℂ × ℝ => F p.1 p.2) (U ×ˢ Set.Icc a b)) :
    ContinuousOn (fun w => ∫ t in a..b, F w t) U  := by
  intro w₀ hw₀
  exact (param_int_continuous_at_of_joint hU hF hw₀).continuousWithinAt

end Problems.residue_thm
