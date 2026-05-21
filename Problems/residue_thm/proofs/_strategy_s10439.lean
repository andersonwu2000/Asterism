import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_circle_kernel_linear_split

namespace Problems.residue_thm

-- Split kernel as `f w / (w - z) = f z * (w - z)⁻¹ + (f w - f z) / (w - z)` on each
-- circle via the abstract sub-goal `circle_kernel_linear_split`, applied with the
-- per-radius continuity-and-off-circle hypotheses; the parent identity then closes
-- by subtracting the two splits (`ring`). Sub-goal is strictly simpler: it isolates
-- the circle-integral linearity + pointwise algebra at a single radius, drops the
-- two-radius coupling, and weakens the `AnalyticOn` hypothesis to plain
-- `ContinuousOn` on one sphere — enough to invoke
-- `circleIntegral.integral_congr` + `circleIntegral.integral_add` +
-- `circleIntegral.integral_const_mul`.
theorem s10439
    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ} (hR : 0 < R)
    (hf : AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀}))
    {z : ℂ} (hzB : z ∈ Metric.ball z₀ R) (hzNe : z ≠ z₀)
    {r : ℝ} (hr_lb : dist z z₀ < r) (hr_ub : r < R)
    {ε : ℝ} (hε_pos : 0 < ε) (hε_lt_d : ε < dist z z₀) :
    (∮ w in C(z₀, r), f w / (w - z))
      - (∮ w in C(z₀, ε), f w / (w - z))
      = f z * ((∮ w in C(z₀, r), (w - z)⁻¹) - (∮ w in C(z₀, ε), (w - z)⁻¹))
        + ((∮ w in C(z₀, r), (f w - f z) / (w - z))
            - (∮ w in C(z₀, ε), (f w - f z) / (w - z)))  := by
  have hr_pos : 0 < r := dist_nonneg.trans_lt hr_lb
  have hd_lt_R : dist z z₀ < R := Metric.mem_ball.mp hzB
  have hε_lt_R : ε < R := hε_lt_d.trans hd_lt_R
  have hcontR : ContinuousOn f (Metric.sphere z₀ r) := by
    apply hf.continuousOn.mono
    intro w hw
    rw [Metric.mem_sphere] at hw
    refine ⟨Metric.mem_ball.mpr (by rw [hw]; exact hr_ub), ?_⟩
    intro hw_eq
    rw [Set.mem_singleton_iff] at hw_eq
    rw [hw_eq, dist_self] at hw
    exact hr_pos.ne hw
  have hcontε : ContinuousOn f (Metric.sphere z₀ ε) := by
    apply hf.continuousOn.mono
    intro w hw
    rw [Metric.mem_sphere] at hw
    refine ⟨Metric.mem_ball.mpr (by rw [hw]; exact hε_lt_R), ?_⟩
    intro hw_eq
    rw [Set.mem_singleton_iff] at hw_eq
    rw [hw_eq, dist_self] at hw
    exact hε_pos.ne hw
  have hzNotr : z ∉ Metric.sphere z₀ r := by
    rw [Metric.mem_sphere]; exact hr_lb.ne
  have hzNotε : z ∉ Metric.sphere z₀ ε := by
    rw [Metric.mem_sphere]; exact hε_lt_d.ne'
  have h_outer := circle_kernel_linear_split (f := f) (z₀ := z₀) (z := z)
      hr_pos hcontR hzNotr
  have h_inner := circle_kernel_linear_split (f := f) (z₀ := z₀) (z := z)
      hε_pos hcontε hzNotε
  rw [h_outer, h_inner]; ring

end Problems.residue_thm
