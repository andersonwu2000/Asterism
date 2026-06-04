import Mathlib
import Problems.Topology.brouwer_fixed_point.Defs

namespace Problems.Topology.brouwer_fixed_point

-- ray_param_zero_on_sphere: on the unit sphere ‖x‖=1 collapses 1-‖x‖²=0,
-- so √(⟨x,vx⟩²+‖vx‖²·0) = ⟨x,vx⟩ (by hvinner ≥ 0, Real.sqrt_sq), giving numerator 0.
-- entry_kind: Builder
theorem ray_param_zero_on_sphere
    {n : ℕ} (hn : 0 < n)
    {v : EuclideanSpace ℝ (Fin n) → EuclideanSpace ℝ (Fin n)}
    (hvcont : ContinuousOn v (Metric.closedBall 0 1))
    (hvne : ∀ x ∈ Metric.closedBall (0 : EuclideanSpace ℝ (Fin n)) 1, v x ≠ 0)
    (hvinner : ∀ x ∈ Metric.sphere (0 : EuclideanSpace ℝ (Fin n)) 1,
        0 ≤ @inner ℝ _ _ x (v x))
    (x : EuclideanSpace ℝ (Fin n))
    (hx : x ∈ Metric.sphere (0 : EuclideanSpace ℝ (Fin n)) 1) :
    (Real.sqrt ((@inner ℝ _ _ x (v x))^2 + ‖v x‖^2 * (1 - ‖x‖^2))
        - @inner ℝ _ _ x (v x)) / ‖v x‖^2 = 0 := by
  have hxnorm : ‖x‖ = 1 := by rwa [Metric.mem_sphere, dist_zero_right] at hx
  have h1 : 1 - ‖x‖^2 = 0 := by rw [hxnorm]; ring
  have hi : 0 ≤ @inner ℝ _ _ x (v x) := hvinner x hx
  have hsqrt : Real.sqrt ((@inner ℝ _ _ x (v x))^2 + ‖v x‖^2 * (1 - ‖x‖^2)) =
               @inner ℝ _ _ x (v x) := by
    rw [h1, mul_zero, add_zero, Real.sqrt_sq hi]
  rw [hsqrt, sub_self, zero_div]

end Problems.Topology.brouwer_fixed_point
