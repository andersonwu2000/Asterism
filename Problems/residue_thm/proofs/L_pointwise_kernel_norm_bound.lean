import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- pointwise_kernel_norm_bound: norm bound ‖f w / (w-z)‖ ≤ C/(‖z-z₀‖-R/2) on sphere,
-- via reverse triangle inequality ‖w-z‖ ≥ ‖z-z₀‖-R/2 and pointwise bound ‖f w‖ ≤ C.
-- entry_kind: Builder
theorem pointwise_kernel_norm_bound
    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ} (hR : 0 < R)
    (hf : AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀}))
    (P : ℂ → ℂ)
    (hP : ∀ z, z ≠ z₀ → ∀ ε : ℝ, 0 < ε → ε < dist z z₀ → ε < R →
        P z = -((2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
              ∮ w in C(z₀, ε), f w / (w - z)))
    (C : ℝ) (hC0 : 0 ≤ C)
    (hC : ∀ w ∈ Metric.sphere z₀ (R/2), ‖f w‖ ≤ C) :
    ∀ z : ℂ, R/2 < ‖z - z₀‖ →
      ∀ w ∈ Metric.sphere z₀ (R/2),
    ‖f w / (w - z)‖ ≤ C / (‖z - z₀‖ - R/2) := by
  intro z hz w hw
  have hw_norm : ‖w - z₀‖ = R / 2 := by
    rw [← dist_eq_norm]; exact Metric.mem_sphere.mp hw
  have hwz_pos : 0 < ‖z - z₀‖ - R / 2 := by linarith
  have hwz_lb : ‖z - z₀‖ - R / 2 ≤ ‖w - z‖ := by
    have h1 := norm_add_le (z - w) (w - z₀)
    simp only [sub_add_sub_cancel] at h1
    rw [norm_sub_rev z w, hw_norm] at h1
    linarith
  have hwz_lt : 0 < ‖w - z‖ := lt_of_lt_of_le hwz_pos hwz_lb
  rw [norm_div]
  gcongr
  · exact hC w hw

end Problems.residue_thm