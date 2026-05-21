import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
-- local_radii_nhd_event: Metric.ball_mem_nhds + dist_triangle close the ∀ᶠ nbhd event
-- Uses the midpoint radius (dist z₁ z₀ + R)/2 as ε-offset to produce a ball around z₁
-- where both z ∈ ball z₀ R and dist z z₀ < (dist z₁ z₀ + R)/2 hold by triangle inequality.
theorem local_radii_nhd_event
    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ} (hR : 0 < R)
    (hf : AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀})) :
    ∀ z₁ ∈ Metric.ball z₀ R,
      ∀ᶠ z in nhds z₁,
        z ∈ Metric.ball z₀ R ∧ dist z z₀ < (dist z₁ z₀ + R) / 2 := by
      intro z₁ hz₁
      simp only [Metric.mem_ball] at hz₁
      have hr : 0 < (dist z₁ z₀ + R) / 2 - dist z₁ z₀ := by linarith
      filter_upwards [Metric.ball_mem_nhds z₁ hr] with z hz
      simp only [Metric.mem_ball] at hz
      exact ⟨Metric.mem_ball.mpr (by linarith [dist_triangle z z₁ z₀]),
             by linarith [dist_triangle z z₁ z₀]⟩
end Problems.residue_thm
