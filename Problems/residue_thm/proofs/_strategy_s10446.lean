import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_circle_dist_lower_bound_near_outside
import Problems.residue_thm.proofs.L_g_bounded_on_sphere

namespace Problems.residue_thm

-- Bound the squared-kernel sup-norm by extracting a uniform `‖g‖` bound on the
-- compact integration sphere and a reverse-triangle denominator bound on the
-- δ-ball around z; combine via M := r * Mg / δ² using ‖deriv (circleMap c r)‖ = r.
-- Sub-goals: (1) g_bounded_on_sphere — compactness+continuity; (2)
-- circle_dist_lower_bound_near_outside — `δ ≤ ‖w-ζ‖` from `r < dist z c`.
theorem s10446
    {g : ℂ → ℂ} {c : ℂ} {r : ℝ} (hr : 0 < r)
    (hg : ContinuousOn g (Metric.sphere c r))
    (z : ℂ) (hz : r < dist z c) :
    ∃ M : ℝ, ∀ ζ ∈ Metric.ball z ((dist z c - r) / 2), ∀ θ : ℝ,
      ‖deriv (circleMap c r) θ • (g (circleMap c r θ) / (circleMap c r θ - ζ) ^ 2)‖ ≤ M  := by
  set δ : ℝ := (dist z c - r) / 2 with hδ_def
  have hδ_pos : 0 < δ := by rw [hδ_def]; linarith
  have h_g_bdd := g_bounded_on_sphere hr hg
  have h_dist_lb := circle_dist_lower_bound_near_outside hr z hz
  obtain ⟨Mg, hMg0, hMg⟩ := h_g_bdd
  refine ⟨r * Mg / δ ^ 2, fun ζ hζ θ => ?_⟩
  have hθ_sphere : circleMap c r θ ∈ Metric.sphere c r := circleMap_mem_sphere c hr.le θ
  have hg_bound : ‖g (circleMap c r θ)‖ ≤ Mg := hMg _ hθ_sphere
  have hd : δ ≤ ‖circleMap c r θ - ζ‖ := h_dist_lb ζ hζ θ
  have hd_pos : 0 < ‖circleMap c r θ - ζ‖ := lt_of_lt_of_le hδ_pos hd
  have h_dn : ‖deriv (circleMap c r) θ‖ = r := by
    rw [deriv_circleMap, norm_mul, norm_circleMap_zero, Complex.norm_I, mul_one, abs_of_pos hr]
  calc ‖deriv (circleMap c r) θ • (g (circleMap c r θ) / (circleMap c r θ - ζ) ^ 2)‖
      = r * (‖g (circleMap c r θ)‖ / ‖circleMap c r θ - ζ‖ ^ 2) := by
        rw [norm_smul, h_dn, norm_div, norm_pow]
    _ ≤ r * (Mg / δ ^ 2) := by
        gcongr
    _ = r * Mg / δ ^ 2 := by ring

end Problems.residue_thm
