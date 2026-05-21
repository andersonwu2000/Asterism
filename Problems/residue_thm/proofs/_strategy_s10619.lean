import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_segment_integral_eq_primitive_diff_in_ball

namespace Problems.residue_thm

-- Telescoping primitive-difference along the closed quadrilateral z₁→z₂→z₃→z₄→z₁.
-- DifferentiableOn ℂ f on a ball gives a primitive F via `hf.isExactOn_ball`
-- (Mathlib `DifferentiableOn.isExactOn_ball`); each straight-line segment integral
-- collapses to `F(end) − F(start)` by FTC along the linear path inside the convex
-- ball, so the 4-cycle telescopes to `F z₁ − F z₁ = 0`. Single sub-goal
-- `segment_integral_eq_primitive_diff_in_ball` packages "primitive ⇒ segment
-- integral = primitive difference" once and is then applied 4 times.
theorem s10619
    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ}
    (hf : DifferentiableOn ℂ f (Metric.ball z₀ R))
    {z₁ z₂ z₃ z₄ : ℂ}
    (h₁ : z₁ ∈ Metric.ball z₀ R)
    (h₂ : z₂ ∈ Metric.ball z₀ R)
    (h₃ : z₃ ∈ Metric.ball z₀ R)
    (h₄ : z₄ ∈ Metric.ball z₀ R) :
    (∫ t in (0:ℝ)..1, f (z₁ + (t:ℂ) * (z₂ - z₁)) * (z₂ - z₁)) +
    (∫ t in (0:ℝ)..1, f (z₂ + (t:ℂ) * (z₃ - z₂)) * (z₃ - z₂)) +
    (∫ t in (0:ℝ)..1, f (z₃ + (t:ℂ) * (z₄ - z₃)) * (z₄ - z₃)) +
    (∫ t in (0:ℝ)..1, f (z₄ + (t:ℂ) * (z₁ - z₄)) * (z₁ - z₄)) = 0  := by
  obtain ⟨F, hF⟩ := hf.isExactOn_ball
  have h12 := segment_integral_eq_primitive_diff_in_ball hF h₁ h₂
  have h23 := segment_integral_eq_primitive_diff_in_ball hF h₂ h₃
  have h34 := segment_integral_eq_primitive_diff_in_ball hF h₃ h₄
  have h41 := segment_integral_eq_primitive_diff_in_ball hF h₄ h₁
  rw [h12, h23, h34, h41]; ring

end Problems.residue_thm
