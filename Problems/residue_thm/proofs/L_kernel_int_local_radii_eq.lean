import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_cauchy_kernel_circle_int_radius_indep

namespace Problems.residue_thm

-- entry_kind: Builder
-- kernel_int_local_radii_eq: radius-independence of the Cauchy kernel integral via
-- cauchy_kernel_circle_int_radius_indep, supplying the four bound conditions from
-- z ∈ ball z₀ R, z₁ ∈ ball z₀ R, and the explicit dist hypothesis.
theorem kernel_int_local_radii_eq
    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ} (hR : 0 < R)
    (hf : AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀})) :
    ∀ z₁ ∈ Metric.ball z₀ R, ∀ z ∈ Metric.ball z₀ R,
      dist z z₀ < (dist z₁ z₀ + R) / 2 →
      (∮ w in C(z₀, (dist z z₀ + R) / 2), f w / (w - z)) =
      (∮ w in C(z₀, (dist z₁ z₀ + R) / 2), f w / (w - z)) := by
  intro z₁ hz₁ z hz hdist
  rw [Metric.mem_ball] at hz₁ hz
  exact cauchy_kernel_circle_int_radius_indep hR hf z (Metric.mem_ball.mpr hz)
    ((dist z z₀ + R) / 2) ((dist z₁ z₀ + R) / 2)
    (by linarith) (by linarith) hdist (by linarith)

end Problems.residue_thm

