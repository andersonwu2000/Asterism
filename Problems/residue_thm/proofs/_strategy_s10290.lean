import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_gamma_sub_a_ne_zero_on_icc
import Problems.residue_thm.proofs.L_integrating_factor_deriv_collapses_to_zero
import Problems.residue_thm.proofs.L_integrating_factor_explicit_deriv

namespace Problems.residue_thm

-- Decompose F'(t) = 0 into (1) denominator ≠ 0, (2) F has the explicit product+chain+FTC
-- derivative expression on Ici t, (3) that expression algebraically collapses to 0.
-- Combinator: substitute the algebra identity into the explicit derivative.
theorem s10290
    {U : Set ℂ} {T : Finset ℂ} {γ : ℝ → ℂ}
    (hU : IsOpen U)
    (hT : ∀ a ∈ T, a ∈ U)
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hmap : Set.MapsTo γ (Set.Icc 0 1) (U \ ↑T))
    (hclosed : γ 0 = γ 1)
    (a : ℂ) (ha : a ∈ T) :
    ∀ t ∈ Set.Ico (0:ℝ) 1,
      HasDerivWithinAt
        (fun t : ℝ => (γ t - a) * Complex.exp (- ∫ s in (0:ℝ)..t, deriv γ s / (γ s - a)))
        0 (Set.Ici t) t  := by
  intro t ht
  have h_icc : t ∈ Set.Icc (0:ℝ) 1 := Set.Ico_subset_Icc_self ht
  have h_ne : γ t - a ≠ 0 :=
    gamma_sub_a_ne_zero_on_icc hU hT hγ hmap hclosed a ha t h_icc
  have h_deriv :=
    integrating_factor_explicit_deriv hU hT hγ hmap hclosed a ha t ht
  have h_zero :=
    integrating_factor_deriv_collapses_to_zero hU hT hγ hmap hclosed a ha t ht h_ne
  exact h_zero ▸ h_deriv




end Problems.residue_thm
