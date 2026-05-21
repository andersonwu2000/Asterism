import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Backward
theorem param_int_continuous_at_of_joint
    {U : Set ℂ} {a b : ℝ} {F : ℂ → ℝ → ℂ}
    (hU : IsOpen U)
    (hF : ContinuousOn (fun p : ℂ × ℝ => F p.1 p.2) (U ×ˢ Set.Icc a b))
    {w₀ : ℂ} (hw₀ : w₀ ∈ U) :
    ContinuousAt (fun w => ∫ t in a..b, F w t) w₀ := by sorry

end Problems.residue_thm
