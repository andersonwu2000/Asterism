import Mathlib
import Problems.Topology.brouwer_fixed_point.Defs
import Problems.Topology.brouwer_fixed_point.proofs.L_ray_param_norm_add_smul_sq_expand
import Problems.Topology.brouwer_fixed_point.proofs.L_ray_param_norm_sq_alg_identity

namespace Problems.Topology.brouwer_fixed_point

-- Expand ‖x + t • v(x)‖² via inner-product polarisation, then reduce the
-- result in (⟨x, v(x)⟩, ‖v(x)‖², ‖x‖²) to a pure ℝ identity.
-- (1) `ray_param_norm_add_smul_sq_expand`: the vector-space expansion
--     ‖x + s • w‖² = ‖x‖² + 2·s·⟨x,w⟩ + s²·‖w‖² (generic, reusable).
-- (2) `ray_param_norm_sq_alg_identity`: pure ℝ identity verifying that the
--     specific choice s = (√(a² + b(1-c)) - a)/b makes the expansion = 1
--     whenever b > 0 and c ≤ 1.
theorem s10824
    {n : ℕ} (hn : 0 < n)
    {v : EuclideanSpace ℝ (Fin n) → EuclideanSpace ℝ (Fin n)}
    (hvcont : ContinuousOn v (Metric.closedBall 0 1))
    (hvne : ∀ x ∈ Metric.closedBall (0 : EuclideanSpace ℝ (Fin n)) 1, v x ≠ 0)
    (hvinner : ∀ x ∈ Metric.sphere (0 : EuclideanSpace ℝ (Fin n)) 1,
        0 ≤ @inner ℝ _ _ x (v x))
    (x : EuclideanSpace ℝ (Fin n))
    (hx : x ∈ Metric.closedBall (0 : EuclideanSpace ℝ (Fin n)) 1) :
    ‖x + ((Real.sqrt ((@inner ℝ _ _ x (v x))^2 + ‖v x‖^2 * (1 - ‖x‖^2))
        - @inner ℝ _ _ x (v x)) / ‖v x‖^2) • v x‖^2 = 1  := by
  have hxle : ‖x‖ ≤ 1 := by rwa [Metric.mem_closedBall, dist_zero_right] at hx
  have hb_pos : (0 : ℝ) < ‖v x‖^2 := pow_pos (norm_pos_iff.mpr (hvne x hx)) 2
  have hc_le : ‖x‖^2 ≤ 1 := by nlinarith [norm_nonneg x]
  have h_expand := ray_param_norm_add_smul_sq_expand x (v x)
    ((Real.sqrt ((@inner ℝ _ _ x (v x))^2 + ‖v x‖^2 * (1 - ‖x‖^2))
        - @inner ℝ _ _ x (v x)) / ‖v x‖^2)
  rw [h_expand]
  exact ray_param_norm_sq_alg_identity
    (@inner ℝ _ _ x (v x)) (‖v x‖^2) (‖x‖^2) hb_pos hc_le

end Problems.Topology.brouwer_fixed_point
