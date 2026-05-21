import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- continuous_on_closed_annulus: annulus ⊆ ball R \ {z₀}; use AnalyticOn.continuousOn + mono
theorem continuous_on_closed_annulus
    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ}
    (hf : AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀}))
    {r₁ r₂ : ℝ} (hr₁ : 0 < r₁) (_hle : r₁ ≤ r₂) (hr₂ : r₂ < R) :
    ContinuousOn f (Metric.closedBall z₀ r₂ \ Metric.ball z₀ r₁) := by
  apply hf.continuousOn.mono
  intro x ⟨hx1, hx2⟩
  simp only [Set.mem_diff, Metric.mem_ball, Set.mem_singleton_iff]
  refine ⟨lt_of_le_of_lt (Metric.mem_closedBall.mp hx1) hr₂, ?_⟩
  intro heq
  apply hx2
  rw [Metric.mem_ball, heq, dist_self]
  exact hr₁

end Problems.residue_thm
