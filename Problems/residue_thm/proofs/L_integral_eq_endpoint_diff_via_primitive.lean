import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Backward
theorem integral_eq_endpoint_diff_via_primitive
    {U : Set ℂ} {γ : ℝ → ℂ} {g G : ℂ → ℂ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hmap : Set.MapsTo γ (Set.Icc 0 1) U)
    (hG : ∀ z ∈ U, HasDerivAt G (g z) z) :
    (∫ t in (0 : ℝ)..1, g (γ t) * deriv γ t) = G (γ 1) - G (γ 0) := by sorry

end Problems.residue_thm
