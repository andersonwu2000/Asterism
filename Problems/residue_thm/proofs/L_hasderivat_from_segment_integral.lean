import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Backward
theorem hasderivat_from_segment_integral
    {Q : ℂ → ℂ} {a : ℂ} {F : ℂ → ℂ}
    (z : ℂ) (hz : z ∈ Set.univ \ ({a} : Set ℂ))
    (h_cont : ContinuousAt Q z)
    (h_seg : ∀ h : ℂ, ‖h‖ < dist z a →
      F (z + h) - F z = ∫ t in (0:ℝ)..1, Q (z + (t : ℂ) * h) * h) :
    HasDerivAt F (Q z) z := by sorry

end Problems.residue_thm
