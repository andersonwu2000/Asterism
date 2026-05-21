import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
theorem gamma_sub_a_has_deriv_within_ici
    {U : Set ℂ} {T : Finset ℂ} {γ : ℝ → ℂ}
    (hU : IsOpen U)
    (hT : ∀ a ∈ T, a ∈ U)
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hmap : Set.MapsTo γ (Set.Icc 0 1) (U \ ↑T))
    (hclosed : γ 0 = γ 1)
    (a : ℂ) (ha : a ∈ T) :
    ∀ t ∈ Set.Ico (0:ℝ) 1,
      HasDerivWithinAt (fun t : ℝ => γ t - a) (deriv γ t) (Set.Ici t) t := by sorry

end Problems.residue_thm
