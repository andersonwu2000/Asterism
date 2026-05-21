import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- cauchy_kernel_diff_at_open_annulus: f w / (w - z') is differentiable at z in the open annulus
-- z lies in ball z₀ R \ {z₀} (so f is analytic there) and z ≠ z' (pole distance argument).
theorem cauchy_kernel_diff_at_open_annulus
    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ} (_hR : 0 < R)
    (hf : AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀})) :
    ∀ z' ∈ Metric.ball z₀ R, ∀ r₁ r₂ : ℝ,
      dist z' z₀ < r₁ → r₁ ≤ r₂ → r₂ < R →
      ∀ z ∈ Metric.ball z₀ r₂ \ Metric.closedBall z₀ r₁,
        DifferentiableAt ℂ (fun w => f w / (w - z')) z := by
  intro z' _hz' r₁ r₂ hr₁z' hr₁r₂ hr₂R z hz
  simp only [Set.mem_diff, Metric.mem_ball, Metric.mem_closedBall, not_le] at hz
  obtain ⟨hzr₂, hzr₁⟩ := hz
  have hzR : z ∈ Metric.ball z₀ R := Metric.mem_ball.mpr (hzr₂.trans hr₂R)
  have hr₁_pos : 0 < r₁ := lt_of_le_of_lt dist_nonneg hr₁z'
  have hzz₀ : z ≠ z₀ := by
    intro h; subst h; simp [dist_self] at hzr₁; linarith
  have hzz' : z ≠ z' := by
    intro h; subst h; linarith
  have hmem : z ∈ Metric.ball z₀ R \ ({z₀} : Set ℂ) :=
    ⟨hzR, by rintro (rfl : z = z₀); exact hzz₀ rfl⟩
  have hopen : IsOpen (Metric.ball z₀ R \ ({z₀} : Set ℂ)) :=
    Metric.isOpen_ball.sdiff isClosed_singleton
  have hfz : DifferentiableAt ℂ f z :=
    (hf.analyticAt (hopen.mem_nhds hmem)).differentiableAt
  exact hfz.div (DifferentiableAt.sub differentiableAt_id (differentiableAt_const z'))
    (sub_ne_zero.mpr hzz')

end Problems.residue_thm
