import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Backward
theorem exp_winding_integral_eq_one
    {U : Set ℂ} {T : Finset ℂ} {γ : ℝ → ℂ}
    (hU : IsOpen U)
    (hT : ∀ a ∈ T, a ∈ U)
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hmap : Set.MapsTo γ (Set.Icc 0 1) (U \ ↑T))
    (hclosed : γ 0 = γ 1)
    (a : ℂ) (ha : a ∈ T) :
    Complex.exp (∫ t in (0:ℝ)..1, deriv γ t / (γ t - a)) = 1 := by sorry

end Problems.residue_thm
