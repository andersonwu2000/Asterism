import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- circle_dist_lower_bound_near_outside: uniform lower bound ‖circleMap c r θ - ζ‖ ≥ δ
-- on the δ-ball around z (exterior point), via reverse triangle inequality.
theorem circle_dist_lower_bound_near_outside
    {c : ℂ} {r : ℝ} (hr : 0 < r) (z : ℂ) (hz : r < dist z c) :
    ∀ ζ ∈ Metric.ball z ((dist z c - r) / 2), ∀ θ : ℝ,
      (dist z c - r) / 2 ≤ ‖circleMap c r θ - ζ‖ := by
  intro ζ hζ θ
  have hζ_lt : dist ζ z < (dist z c - r) / 2 := by rwa [Metric.mem_ball] at hζ
  have hw_dist : dist z c - r ≤ ‖circleMap c r θ - z‖ := by
    have hcirc : ‖circleMap c r θ - c‖ = r := by
      simp [circleMap, hr.le]
    have tri := dist_triangle z (circleMap c r θ) c
    rw [dist_eq_norm, dist_eq_norm (circleMap c r θ) c] at tri
    linarith [norm_sub_rev z (circleMap c r θ), dist_eq_norm z (circleMap c r θ),
              norm_sub_rev z c, dist_eq_norm z c]


  have tri2 : ‖circleMap c r θ - z‖ - ‖ζ - z‖ ≤ ‖circleMap c r θ - ζ‖ := by
    have h := norm_sub_norm_le (circleMap c r θ - z) (ζ - z)
    simp only [sub_sub_sub_cancel_right] at h
    linarith
  linarith [dist_eq_norm ζ z]

end Problems.residue_thm
