import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_integrating_factor_continuous_on_icc
import Problems.residue_thm.proofs.L_integrating_factor_has_deriv_right_zero

namespace Problems.residue_thm

-- Show F(t) := (γ t - a) · exp(-∫₀ᵗ deriv γ s/(γ s - a)) equals F(0) on [0,1] by
-- proving F is continuous on [0,1] and has right-derivative 0 on [0,1), then
-- applying `constant_of_has_deriv_right_zero`. The derivative computation
-- (product + chain rule + FTC) is delegated to the deriv-zero sub-goal; the
-- continuity sub-goal handles regularity at the endpoints.
theorem s10287
    {U : Set ℂ} {T : Finset ℂ} {γ : ℝ → ℂ}
    (hU : IsOpen U)
    (hT : ∀ a ∈ T, a ∈ U)
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hmap : Set.MapsTo γ (Set.Icc 0 1) (U \ ↑T))
    (hclosed : γ 0 = γ 1)
    (a : ℂ) (ha : a ∈ T) :
    ∀ t ∈ Set.Icc (0:ℝ) 1,
      (γ t - a) * Complex.exp (- ∫ s in (0:ℝ)..t, deriv γ s / (γ s - a))
        = (γ 0 - a) * Complex.exp (- ∫ s in (0:ℝ)..(0:ℝ), deriv γ s / (γ s - a))  := by
  have h_cont :=
    integrating_factor_continuous_on_icc hU hT hγ hmap hclosed a ha
  have h_deriv :=
    integrating_factor_has_deriv_right_zero hU hT hγ hmap hclosed a ha
  exact constant_of_has_deriv_right_zero h_cont h_deriv

end Problems.residue_thm
