import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- Direct set-extensionality leaf: the cone over the unit sphere with radii in (0,1]
-- is exactly the punctured closed unit ball. (⊆) `‖r•x‖ = r·1 = r ≤ 1` and `r•x ≠ 0`
-- since `r > 0`, `‖x‖ = 1`; (⊇) for `y ≠ 0`, take `r = ‖y‖ ∈ (0,1]`, `x = ‖y‖⁻¹•y`
-- (`‖x‖ = 1`), then `‖y‖ • ‖y‖⁻¹ • y = y`. Pure normed-space algebra — no sub-goals.
theorem s11488 :
    { y : E | ∃ r ∈ Set.Ioc (0 : ℝ) 1, ∃ x ∈ Metric.sphere (0 : E) 1, y = r • x }
      = Metric.closedBall (0 : E) 1 \ {0}  := by
  ext y
  simp only [Set.mem_setOf_eq, Set.mem_diff, Metric.mem_closedBall, dist_zero_right,
    Metric.mem_sphere, Set.mem_singleton_iff]
  constructor
  · rintro ⟨r, ⟨hr0, hr1⟩, x, hx, rfl⟩
    refine ⟨?_, ?_⟩
    · rw [norm_smul, Real.norm_eq_abs, abs_of_pos hr0, hx, mul_one]; exact hr1
    · exact smul_ne_zero (ne_of_gt hr0) (by rw [← norm_pos_iff, hx]; norm_num)
  · rintro ⟨hy1, hy0⟩
    have hyn : 0 < ‖y‖ := norm_pos_iff.mpr hy0
    refine ⟨‖y‖, ⟨hyn, hy1⟩, ‖y‖⁻¹ • y, ?_, ?_⟩
    · rw [norm_smul, norm_inv, Real.norm_eq_abs, abs_norm,
        inv_mul_cancel₀ (ne_of_gt hyn)]
    · rw [smul_smul, mul_inv_cancel₀ (ne_of_gt hyn), one_smul]

end Problems.Geometry.banach_tarski
