import Mathlib
import Problems.Topology.brouwer_fixed_point.Defs

namespace Problems.Topology.brouwer_fixed_point

-- entry_kind: Builder
-- sphere_inner_diff_nonneg: inner product ⟨x, x - f(x)⟩ ≥ 0 for x on unit sphere,
-- using ‖x‖ = 1, ‖f(x)‖ ≤ 1, and Cauchy-Schwarz: ⟨x,f(x)⟩ ≤ ‖x‖‖f(x)‖ ≤ 1
theorem sphere_inner_diff_nonneg
    {n : ℕ} (hn : 0 < n)
    {f : EuclideanSpace ℝ (Fin n) → EuclideanSpace ℝ (Fin n)}
    (hmaps : Set.MapsTo f
        (Metric.closedBall (0 : EuclideanSpace ℝ (Fin n)) 1)
        (Metric.closedBall (0 : EuclideanSpace ℝ (Fin n)) 1)) :
    ∀ x ∈ Metric.sphere (0 : EuclideanSpace ℝ (Fin n)) 1,
      0 ≤ @inner ℝ _ _ x (x - f x) := by
  intro x hx
  have hxnorm : ‖x‖ = 1 := by
    rwa [Metric.mem_sphere, dist_zero_right] at hx
  have hfx : f x ∈ Metric.closedBall (0 : EuclideanSpace ℝ (Fin n)) 1 :=
    hmaps (Metric.sphere_subset_closedBall hx)
  have hfxnorm : ‖f x‖ ≤ 1 := by
    rwa [Metric.mem_closedBall, dist_zero_right] at hfx
  rw [inner_sub_right, real_inner_self_eq_norm_sq, hxnorm, one_pow]
  have hcs : @inner ℝ _ _ x (f x) ≤ 1 :=
    calc @inner ℝ _ _ x (f x)
        ≤ |@inner ℝ _ _ x (f x)| := le_abs_self _
      _ ≤ ‖x‖ * ‖f x‖ := abs_real_inner_le_norm x (f x)
      _ ≤ 1 * 1 := by nlinarith [norm_nonneg (f x)]
      _ = 1 := mul_one 1
  linarith

end Problems.Topology.brouwer_fixed_point
