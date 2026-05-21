import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Backward
theorem primitive_exists_on_simply_connected
    {U : Set ℂ} {f : ℂ → ℂ}
    (hU : IsOpen U) (hSC : SimplyConnectedSpace U)
    (hf : AnalyticOn ℂ f U) :
    ∃ F : ℂ → ℂ, ∀ z ∈ U, HasDerivAt F (f z) z := by sorry

end Problems.residue_thm
