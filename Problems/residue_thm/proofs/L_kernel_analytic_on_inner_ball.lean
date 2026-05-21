import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
-- kernel_analytic_on_inner_ball: AnalyticOn.div combining hf.mono (ball shrink) and
-- sub-const analyticity; w - z ≠ 0 since dist w z₀ < dist z z₀ on the smaller ball.
theorem kernel_analytic_on_inner_ball
    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ}
    (hf : AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀}))
    {z : ℂ} (hz : z ≠ z₀) :
    AnalyticOn ℂ (fun w => f w / (w - z))
      (Metric.ball z₀ (min R (dist z z₀)) \ {z₀}) := by
  apply AnalyticOn.div
  · exact hf.mono (Set.diff_subset_diff_left
        (Metric.ball_subset_ball (min_le_left R (dist z z₀))))
  · exact analyticOn_id.sub analyticOn_const
  · intro w hw
    have hlt : dist w z₀ < dist z z₀ :=
      (Metric.mem_ball.mp hw.1).trans_le (min_le_right R _)
    intro heq
    rw [sub_eq_zero] at heq
    rw [heq] at hlt
    exact lt_irrefl _ hlt

end Problems.residue_thm
