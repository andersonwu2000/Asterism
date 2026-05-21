import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_pointwise_kernel_norm_bound

namespace Problems.residue_thm

-- ML-style estimate: pointwise kernel bound `‖f w / (w-z)‖ ≤ C/(‖z-z₀‖-R/2)` on the sphere
-- (sub-goal) lifted by `circleIntegral.norm_integral_le_of_norm_le_const` and reassociated by ring.
theorem s10444
    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ} (hR : 0 < R)
    (hf : AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀}))
    (P : ℂ → ℂ)
    (hP : ∀ z, z ≠ z₀ → ∀ ε : ℝ, 0 < ε → ε < dist z z₀ → ε < R →
        P z = -((2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
              ∮ w in C(z₀, ε), f w / (w - z)))
    (C : ℝ) (hC0 : 0 ≤ C)
    (hC : ∀ w ∈ Metric.sphere z₀ (R/2), ‖f w‖ ≤ C) :
    ∀ z : ℂ, R/2 < ‖z - z₀‖ →
      ‖∮ w in C(z₀, R/2), f w / (w - z)‖
        ≤ 2 * Real.pi * (R/2) * C / (‖z - z₀‖ - R/2)  := by
  intro z hz
  have hr : (0:ℝ) ≤ R/2 := by linarith
  have h_pointwise_kernel_norm_bound :=
    pointwise_kernel_norm_bound hR hf P hP C hC0 hC z hz
  have h_int :=
    circleIntegral.norm_integral_le_of_norm_le_const hr h_pointwise_kernel_norm_bound
  calc ‖∮ w in C(z₀, R/2), f w / (w - z)‖
      ≤ 2 * Real.pi * (R/2) * (C / (‖z - z₀‖ - R/2)) := h_int
    _ = 2 * Real.pi * (R/2) * C / (‖z - z₀‖ - R/2) := by ring

end Problems.residue_thm
