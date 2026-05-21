import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_pointwise_kernel_bound

namespace Problems.residue_thm

-- Pointwise kernel-decay + ML inequality. On the sphere of radius r, reverse
-- triangle gives `|w - z| ≥ dist z z₀ - r > 0`, so `‖f w / (w - z)‖ ≤ M / (dist z z₀ - r)`;
-- `circleIntegral.norm_integral_le_of_norm_le_const` lifts to a `2π·r` factor, and
-- `mul_div_assoc` reassociates to the stated bound.
theorem s10440
    {f : ℂ → ℂ} {z₀ : ℂ} {r M : ℝ} (hr : 0 ≤ r)
    (hf : ∀ w ∈ Metric.sphere z₀ r, ‖f w‖ ≤ M)
    {z : ℂ} (hz : r < dist z z₀) :
    ‖∮ w in C(z₀, r), f w / (w - z)‖ ≤ 2 * Real.pi * r * M / (dist z z₀ - r)  := by
  have h_bound := pointwise_kernel_bound hr hf hz
  have h_int := circleIntegral.norm_integral_le_of_norm_le_const hr h_bound
  rwa [← mul_div_assoc] at h_int

end Problems.residue_thm
