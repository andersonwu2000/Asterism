import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_chain_rule_g_circ_gamma_on_uicc
import Problems.residue_thm.proofs.L_g_gamma_integrand_interval_integrable

namespace Problems.residue_thm

-- FTC + chain rule: F(t) := G(γ t) has derivative g(γ t)·γ'(t); apply
-- intervalIntegral.integral_eq_sub_of_hasDerivAt to get F(1) - F(0).
theorem s10291
    {U : Set ℂ} {γ : ℝ → ℂ} {g G : ℂ → ℂ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hmap : Set.MapsTo γ (Set.Icc 0 1) U)
    (hG : ∀ z ∈ U, HasDerivAt G (g z) z) :
    (∫ t in (0 : ℝ)..1, g (γ t) * deriv γ t) = G (γ 1) - G (γ 0)  := by
  have h_chain : ∀ t ∈ Set.uIcc (0:ℝ) 1,
      HasDerivAt (fun s => G (γ s)) (g (γ t) * deriv γ t) t :=
    chain_rule_g_circ_gamma_on_uicc hγ hmap hG
  have h_int : IntervalIntegrable (fun t => g (γ t) * deriv γ t)
      MeasureTheory.volume 0 1 :=
    g_gamma_integrand_interval_integrable hγ hmap hG
  exact intervalIntegral.integral_eq_sub_of_hasDerivAt h_chain h_int
end Problems.residue_thm
