import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Backward
theorem cauchy_integral_simply_connected_zero
    {U : Set ℂ} {T : Finset ℂ} {f : ℂ → ℂ} {γ : ℝ → ℂ}
    (hU : IsOpen U) (hsc : SimplyConnectedSpace ↥U)
    (hT : ∀ a ∈ T, a ∈ U)
    (hf : AnalyticOn ℂ f (U \ ↑T))
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hmap : Set.MapsTo γ (Set.Icc 0 1) (U \ ↑T))
    (hclosed : γ 0 = γ 1)
    {g : ℂ → ℂ} (hg : AnalyticOn ℂ g U) :
    (∫ t in (0 : ℝ)..1, g (γ t) * deriv γ t) = 0 := by sorry

end Problems.residue_thm
