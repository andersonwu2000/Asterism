import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Backward
theorem param_int_continuous_on_open_of_joint
    {U : Set ℂ} {a b : ℝ} {F : ℂ → ℝ → ℂ}
    (hU : IsOpen U)
    (hF : ContinuousOn (fun p : ℂ × ℝ => F p.1 p.2) (U ×ˢ Set.Icc a b)) :
    ContinuousOn (fun w => ∫ t in a..b, F w t) U := by sorry

end Problems.residue_thm
