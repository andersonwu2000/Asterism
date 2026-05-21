import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Backward
theorem integrating_factor_eq_initial_value
    {U : Set ℂ} {T : Finset ℂ} {γ : ℝ → ℂ}
    (hU : IsOpen U)
    (hT : ∀ a ∈ T, a ∈ U)
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hmap : Set.MapsTo γ (Set.Icc 0 1) (U \ ↑T))
    (hclosed : γ 0 = γ 1)
    (a : ℂ) (ha : a ∈ T) :
    ∀ t ∈ Set.Icc (0:ℝ) 1,
      (γ t - a) * Complex.exp (- ∫ s in (0:ℝ)..t, deriv γ s / (γ s - a))
        = (γ 0 - a) * Complex.exp (- ∫ s in (0:ℝ)..(0:ℝ), deriv γ s / (γ s - a)) := by sorry

end Problems.residue_thm
