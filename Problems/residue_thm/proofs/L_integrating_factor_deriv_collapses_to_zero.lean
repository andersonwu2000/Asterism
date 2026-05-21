import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
theorem integrating_factor_deriv_collapses_to_zero
    {U : Set ℂ} {T : Finset ℂ} {γ : ℝ → ℂ}
    (hU : IsOpen U)
    (hT : ∀ a ∈ T, a ∈ U)
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hmap : Set.MapsTo γ (Set.Icc 0 1) (U \ ↑T))
    (hclosed : γ 0 = γ 1)
    (a : ℂ) (ha : a ∈ T) :
    ∀ t ∈ Set.Ico (0:ℝ) 1, γ t - a ≠ 0 →
      deriv γ t * Complex.exp (- ∫ s in (0:ℝ)..t, deriv γ s / (γ s - a))
       + (γ t - a) * (Complex.exp (- ∫ s in (0:ℝ)..t, deriv γ s / (γ s - a))
                          * (-(deriv γ t / (γ t - a)))) = 0 := by grind

end Problems.residue_thm
