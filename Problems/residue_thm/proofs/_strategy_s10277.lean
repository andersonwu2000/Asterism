import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- Direct application of `Complex.circleIntegral_eq_of_differentiable_on_annulus_off_countable`
-- with the closed annulus `closedBall z₀ r₂ \ ball z₀ r₁` contained in the punctured ball
-- `ball z₀ R \ {z₀}`. AnalyticOn → ContinuousOn (annulus) and DifferentiableAt (open annulus).
theorem s10277
    {f : ℂ → ℂ} {z₀ : ℂ} {R r₁ r₂ : ℝ}
    (hf : AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀}))
    (hr₁ : 0 < r₁) (hr₁R : r₁ < R) (hr₂ : 0 < r₂) (hr₂R : r₂ < R)
    (hle : r₁ ≤ r₂) :
    (∮ z in C(z₀, r₁), f z) = (∮ z in C(z₀, r₂), f z)  := by
  have hsub : Metric.closedBall z₀ r₂ \ Metric.ball z₀ r₁ ⊆
      Metric.ball z₀ R \ {z₀} := by
    intro z hz
    refine ⟨?_, ?_⟩
    · rw [Metric.mem_ball]
      have : dist z z₀ ≤ r₂ := Metric.mem_closedBall.mp hz.1
      linarith
    · intro hzeq
      have : dist z z₀ < r₁ := by
        rw [hzeq, Set.mem_singleton_iff] at *
        rw [dist_self]; exact hr₁
      exact hz.2 (Metric.mem_ball.mpr this)
  have hcont : ContinuousOn f (Metric.closedBall z₀ r₂ \ Metric.ball z₀ r₁) :=
    (hf.mono hsub).continuousOn
  have hdiff : ∀ z ∈ (Metric.ball z₀ r₂ \ Metric.closedBall z₀ r₁) \ (∅ : Set ℂ),
      DifferentiableAt ℂ f z := by
    intro z hz
    have hz' : z ∈ Metric.ball z₀ R \ {z₀} := by
      refine ⟨?_, ?_⟩
      · rw [Metric.mem_ball]
        have : dist z z₀ < r₂ := Metric.mem_ball.mp hz.1.1
        linarith
      · intro hzeq
        apply hz.1.2
        rw [hzeq, Metric.mem_closedBall, dist_self]
        exact le_of_lt hr₁
    have hopen : IsOpen (Metric.ball z₀ R \ {z₀}) :=
      Metric.isOpen_ball.sdiff (T1Space.t1 z₀)
    exact ((hf.analyticAt (hopen.mem_nhds hz')).differentiableAt)
  exact (Complex.circleIntegral_eq_of_differentiable_on_annulus_off_countable
    hr₁ hle Set.countable_empty hcont hdiff).symm

end Problems.residue_thm
