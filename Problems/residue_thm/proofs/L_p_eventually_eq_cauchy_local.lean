import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
-- p_eventually_eq_cauchy_local: pick ε = min(dist z z₀ / 2, R / 2); in ball of
-- radius dist z z₀ / 4 around z every ζ has ε < dist ζ z₀, so hP applies pointwise.
theorem p_eventually_eq_cauchy_local
    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ} (hR : 0 < R)
    (hf : AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀}))
    (P : ℂ → ℂ)
    (hP : ∀ z, z ≠ z₀ → ∀ ε : ℝ, 0 < ε → ε < dist z z₀ → ε < R →
        P z = -((2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
              ∮ w in C(z₀, ε), f w / (w - z)))
    (z : ℂ) (hzne : z ≠ z₀) :
    ∃ ε : ℝ, 0 < ε ∧ ε < R ∧ ε < dist z z₀ ∧
      P =ᶠ[nhds z]
        (fun ζ => -((2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
              ∮ w in C(z₀, ε), f w / (w - ζ))) := by
  have hdist : 0 < dist z z₀ := by rwa [dist_pos]
  refine ⟨min (dist z z₀ / 2) (R / 2), ?_, ?_, ?_, ?_⟩
  · positivity
  · exact lt_of_le_of_lt (min_le_right _ _) (by linarith)
  · exact lt_of_le_of_lt (min_le_left _ _) (by linarith)
  · apply Filter.Eventually.mono (Metric.ball_mem_nhds z (show (0 : ℝ) < dist z z₀ / 4 by linarith))
    intro ζ hζ
    have hζball : dist ζ z < dist z z₀ / 4 := Metric.mem_ball.mp hζ
    have hεpos : 0 < min (dist z z₀ / 2) (R / 2) := by positivity
    have hε_lt_distζ : min (dist z z₀ / 2) (R / 2) < dist ζ z₀ := by
      apply lt_of_le_of_lt (min_le_left _ _)
      have h1 : dist z z₀ ≤ dist z ζ + dist ζ z₀ := dist_triangle z ζ z₀
      have h2 : dist z ζ < dist z z₀ / 4 := by rwa [dist_comm]
      linarith
    have hζne : ζ ≠ z₀ := by
      intro h; rw [h, dist_comm] at hζball; linarith
    exact hP ζ hζne _ hεpos hε_lt_distζ (lt_of_le_of_lt (min_le_right _ _) (by linarith))


end Problems.residue_thm
