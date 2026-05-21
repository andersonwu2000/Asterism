import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Backward
theorem holomorphic_extension_subtract_poles
    {U : Set ℂ} {T : Finset ℂ} {f : ℂ → ℂ}
    (hU : IsOpen U)
    (hT : ∀ a ∈ T, a ∈ U)
    (hf : AnalyticOn ℂ f (U \ ↑T)) :
    ∃ g : ℂ → ℂ, AnalyticOn ℂ g U ∧
      ∀ z ∈ U \ ↑T, g z = f z - ∑ a ∈ T, Complex.residue f a / (z - a) := by sorry

end Problems.residue_thm
