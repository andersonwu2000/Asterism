import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_circle_integrable_const_mul_inv
import Problems.residue_thm.proofs.L_circle_integrable_diff_div
import Problems.residue_thm.proofs.L_kernel_split_pointwise

namespace Problems.residue_thm

-- Pointwise: on the sphere, f w / (w - z) = f z * (w - z)⁻¹ + (f w - f z) / (w - z)
-- (since hz puts z off the sphere, hence w - z ≠ 0). Lift via circle integral
-- linearity: integral_congr → integral_add → integral_const_mul. Sub-goals isolate
-- (a) the pointwise field identity, (b)/(c) per-summand circle-integrability.
theorem s10443
    {f : ℂ → ℂ} {z₀ z : ℂ} {ρ : ℝ}
    (hρ : 0 < ρ)
    (hfcont : ContinuousOn f (Metric.sphere z₀ ρ))
    (hz : z ∉ Metric.sphere z₀ ρ) :
    (∮ w in C(z₀, ρ), f w / (w - z))
      = f z * (∮ w in C(z₀, ρ), (w - z)⁻¹)
        + (∮ w in C(z₀, ρ), (f w - f z) / (w - z))  := by
  have h_pointwise := kernel_split_pointwise hρ hfcont hz
  have h_int_const_mul_inv := circle_integrable_const_mul_inv hρ hfcont hz
  have h_int_diff_div := circle_integrable_diff_div hρ hfcont hz
  have h_eq : (∮ w in C(z₀, ρ), f w / (w - z))
      = (∮ w in C(z₀, ρ), f z * (w - z)⁻¹ + (f w - f z) / (w - z)) :=
    circleIntegral.integral_congr hρ.le h_pointwise
  rw [h_eq, circleIntegral.integral_add h_int_const_mul_inv h_int_diff_div,
      circleIntegral.integral_const_mul]

end Problems.residue_thm
