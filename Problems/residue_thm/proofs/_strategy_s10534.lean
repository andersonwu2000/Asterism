import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_path_int_integrand_interval_integrable
import Problems.residue_thm.proofs.L_primitive_comp_path_continuous_on
import Problems.residue_thm.proofs.L_primitive_comp_path_hasderivat_interior

namespace Problems.residue_thm

-- FTC along a C¹ path inside a ball: F primitive on ball ⇒ ∫ f(γ)·γ' = F(γ b) − F(γ a).
-- Splits via `intervalIntegral.integral_eq_sub_of_hasDerivAt_of_le hab` into
--   (a) ContinuousOn (F ∘ γ) on Icc a b,
--   (b) chain rule HasDerivAt (F ∘ γ) at every x ∈ Ioo a b (interior unlocks DifferentiableAt
--       since Icc a b ∈ 𝓝 x, sidestepping the derivWithin/junk-endpoint trap),
--   (c) IntervalIntegrable (fun t => f (γ t) * deriv γ t) on a..b.
theorem s10534
    {f F : ℂ → ℂ} {z₀ : ℂ} {R : ℝ} {γ : ℝ → ℂ} {a b : ℝ}
    (hab : a ≤ b)
    (hF : ∀ z ∈ Metric.ball z₀ R, HasDerivAt F (f z) z)
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc a b))
    (hγU : Set.MapsTo γ (Set.Icc a b) (Metric.ball z₀ R)) :
    (∫ t in a..b, f (γ t) * deriv γ t) = F (γ b) - F (γ a)  := by
  have h_cont := primitive_comp_path_continuous_on hab hF hγ hγU
  have h_deriv := primitive_comp_path_hasderivat_interior hab hF hγ hγU
  have h_int := path_int_integrand_interval_integrable hab hF hγ hγU
  exact intervalIntegral.integral_eq_sub_of_hasDerivAt_of_le hab h_cont h_deriv h_int

end Problems.residue_thm
