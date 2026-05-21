import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- cauchy_kernel_diff_outer_inner: outer Cauchy kernel integral = 2πi,
-- inner integral = 0 by Goursat (z outside ε-disk)
theorem cauchy_kernel_diff_outer_inner
    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ} (hR : 0 < R)
    (hf : AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀}))
    {z : ℂ} (hzB : z ∈ Metric.ball z₀ R) (hzNe : z ≠ z₀)
    {r : ℝ} (hr_lb : dist z z₀ < r) (hr_ub : r < R)
    {ε : ℝ} (hε_pos : 0 < ε) (hε_lt_d : ε < dist z z₀) :
    (∮ w in C(z₀, r), (w - z)⁻¹) - (∮ w in C(z₀, ε), (w - z)⁻¹)
      = 2 * (Real.pi : ℂ) * Complex.I := by
  have hz_in_r : z ∈ Metric.ball z₀ r := Metric.mem_ball.mpr hr_lb
  have outer : (∮ w in C(z₀, r), (w - z)⁻¹) = 2 * ↑Real.pi * Complex.I :=
    circleIntegral.integral_sub_inv_of_mem_ball hz_in_r
  have hz_not_in_closed_eps : ∀ w ∈ Metric.closedBall z₀ ε, w ≠ z := fun w hw heq => by
    rw [← heq] at hε_lt_d
    exact absurd (Metric.mem_closedBall.mp hw) (not_le.mpr hε_lt_d)
  have inner : (∮ w in C(z₀, ε), (w - z)⁻¹) = 0 := by
    apply DiffContOnCl.circleIntegral_eq_zero hε_pos.le
    constructor
    · intro w hw
      apply DifferentiableAt.differentiableWithinAt
      exact (differentiableAt_id.sub_const z).inv
        (sub_ne_zero.mpr (hz_not_in_closed_eps w (Metric.ball_subset_closedBall hw)))
    · apply ContinuousOn.mono
        ((continuousOn_id.sub continuousOn_const).inv₀
          (fun w hw => sub_ne_zero.mpr (hz_not_in_closed_eps w hw)))
      exact Metric.closure_ball_subset_closedBall
  rw [outer, inner, sub_zero]

end Problems.residue_thm
