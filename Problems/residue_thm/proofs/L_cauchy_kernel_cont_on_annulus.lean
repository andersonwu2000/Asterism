import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- cauchy_kernel_cont_on_annulus: ContinuousOn.div applied to analytic f and non-vanishing (w - z')
-- on a closed annulus disjoint from z'; annulus ⊆ ball z₀ R \ {z₀} so hf gives continuity of f,
-- and dist z' z₀ < r₁ ≤ dist w z₀ ensures w ≠ z' throughout.
-- entry_kind: Builder
theorem cauchy_kernel_cont_on_annulus
    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ} (hR : 0 < R)
    (hf : AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀})) :
    ∀ z' ∈ Metric.ball z₀ R, ∀ r₁ r₂ : ℝ,
      dist z' z₀ < r₁ → r₁ ≤ r₂ → r₂ < R →
      ContinuousOn (fun w => f w / (w - z'))
        (Metric.closedBall z₀ r₂ \ Metric.ball z₀ r₁) := by
  intro z' hz' r₁ r₂ hr₁ hr₁r₂ hr₂
  apply ContinuousOn.div
  · apply hf.continuousOn.mono
    intro w hw
    simp only [Set.mem_diff, Metric.mem_closedBall, Metric.mem_ball,
               Set.mem_singleton_iff] at hw ⊢
    refine ⟨lt_of_le_of_lt hw.1 hr₂, ?_⟩
    intro heq
    subst heq
    simp only [dist_self] at hw
    linarith [dist_nonneg (x := z') (y := w), hw.2]
  · exact continuousOn_id.sub continuousOn_const
  · intro w hw
    simp only [Set.mem_diff, Metric.mem_closedBall, Metric.mem_ball] at hw
    have hdist : r₁ ≤ dist w z₀ := not_lt.mp hw.2
    simp only [sub_ne_zero]
    intro heq
    rw [heq] at hdist
    linarith

end Problems.residue_thm
