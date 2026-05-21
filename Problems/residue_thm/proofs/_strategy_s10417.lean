import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_cauchy_kernel_circle_int_radius_indep

namespace Problems.residue_thm

-- Reduce to radius-independence for the Cauchy kernel `w ↦ f w / (w - z)` on
-- `(dist z z₀, R)`, instantiating it at the canonical mid-radius and `r`.
-- The (2πi)⁻¹ factor cancels via `congr`/`rw`; the analytic core is the sub-goal.
theorem s10417
    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ} (hR : 0 < R)
    (hf : AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀})) :
    ∀ z, z ∈ Metric.ball z₀ R → ∀ r : ℝ, dist z z₀ < r → r < R →
      (2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
        (∮ w in C(z₀, (dist z z₀ + R) / 2), f w / (w - z)) =
      (2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
        (∮ w in C(z₀, r), f w / (w - z))  := by
  intro z hz r hzr hrR
  have hzlt_R : dist z z₀ < R := Metric.mem_ball.mp hz
  have hmid_lo : dist z z₀ < (dist z z₀ + R) / 2 := by linarith
  have hmid_hi : (dist z z₀ + R) / 2 < R := by linarith
  have h_indep := cauchy_kernel_circle_int_radius_indep hR hf
  have h := h_indep z hz ((dist z z₀ + R) / 2) r hmid_lo hmid_hi hzr hrR
  rw [h]

end Problems.residue_thm
