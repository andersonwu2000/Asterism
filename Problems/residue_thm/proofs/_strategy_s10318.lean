import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_chain_rule_interior
import Problems.residue_thm.proofs.L_continuous_on_f_circ_gamma
import Problems.residue_thm.proofs.L_interval_integrable_integrand

namespace Problems.residue_thm

-- FTC along a C¹ path: continuity of F∘γ, interior chain rule for (F∘γ)' = f(γ)·γ',
-- and integrability of the integrand combine via integral_eq_sub_of_hasDerivAt_of_le.
theorem s10318
    {U : Set ℂ} {f F : ℂ → ℂ} {γ : ℝ → ℂ}
    (hU : IsOpen U)
    (hF : ∀ z ∈ U, HasDerivAt F (f z) z)
    (hγC1 : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hγU : Set.MapsTo γ (Set.Icc 0 1) U) :
    (∫ t in (0:ℝ)..1, f (γ t) * deriv γ t) = F (γ 1) - F (γ 0)  := by
  have h_cont := continuous_on_f_circ_gamma hU hF hγC1 hγU
  have h_chain := chain_rule_interior hU hF hγC1 hγU
  have h_int := interval_integrable_integrand hU hF hγC1 hγU
  exact intervalIntegral.integral_eq_sub_of_hasDerivAt_of_le zero_le_one h_cont h_chain h_int

end Problems.residue_thm
