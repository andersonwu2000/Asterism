import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_integrable_f_along_gamma
import Problems.residue_thm.proofs.L_integrable_pole_summand_along_gamma
import Problems.residue_thm.proofs.L_integral_linearity_finset_residue

namespace Problems.residue_thm

-- Integral linearity: pointwise distribute `* deriv γ t`, split the integral
-- of a difference, swap finite sum with integral, and pull each residue
-- constant out — granted integrability of the main and pole-summand integrands.
theorem s10286
    {U : Set ℂ} {T : Finset ℂ} {f : ℂ → ℂ} {γ : ℝ → ℂ}
    (hU : IsOpen U) (hsc : SimplyConnectedSpace ↥U)
    (hT : ∀ a ∈ T, a ∈ U)
    (hf : AnalyticOn ℂ f (U \ ↑T))
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hmap : Set.MapsTo γ (Set.Icc 0 1) (U \ ↑T))
    (hclosed : γ 0 = γ 1) :
    (∫ t in (0 : ℝ)..1,
      (f (γ t) - ∑ a ∈ T, Complex.residue f a / (γ t - a)) * deriv γ t) =
      (∫ t in (0 : ℝ)..1, f (γ t) * deriv γ t) -
      ∑ a ∈ T, (∫ t in (0 : ℝ)..1, deriv γ t / (γ t - a)) * Complex.residue f a  := by
  have h_main := integrable_f_along_gamma hU hsc hT hf hγ hmap hclosed
  have h_pole := integrable_pole_summand_along_gamma hU hsc hT hf hγ hmap hclosed
  exact integral_linearity_finset_residue hU hsc hT hf hγ hmap hclosed h_main h_pole

end Problems.residue_thm
