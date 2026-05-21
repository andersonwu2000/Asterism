import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Backward
theorem primitive_along_closed_path_simply_connected
    {U : Set ℂ} {g : ℂ → ℂ} {γ : ℝ → ℂ}
    (hU : IsOpen U)
    (hSC : SimplyConnectedSpace ↥U)
    (hg : AnalyticOn ℂ g U)
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hmaps : Set.MapsTo γ (Set.Icc 0 1) U)
    (hclosed : γ 0 = γ 1) :
    ∃ F : ℝ → ℂ,
      ContinuousOn F (Set.Icc (0 : ℝ) 1) ∧
      (∀ t ∈ Set.Ioo (0 : ℝ) 1, HasDerivAt F (g (γ t) * deriv γ t) t) ∧
      F 0 = F 1 := by sorry

end Problems.residue_thm
