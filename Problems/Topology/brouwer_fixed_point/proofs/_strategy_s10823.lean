import Mathlib
import Problems.Topology.brouwer_fixed_point.Defs
import Problems.Topology.brouwer_fixed_point.proofs.L_ray_param_norm_sq_eq_one

namespace Problems.Topology.brouwer_fixed_point

-- Reduce ‖y‖ = 1 to ‖y‖² = 1 by squaring; norm_nonneg + nlinarith closes the
-- positive root, leaving the substantive algebraic identity as one sub-goal.
theorem s10823
    {n : ℕ} (hn : 0 < n)
    {v : EuclideanSpace ℝ (Fin n) → EuclideanSpace ℝ (Fin n)}
    (hvcont : ContinuousOn v (Metric.closedBall 0 1))
    (hvne : ∀ x ∈ Metric.closedBall (0 : EuclideanSpace ℝ (Fin n)) 1, v x ≠ 0)
    (hvinner : ∀ x ∈ Metric.sphere (0 : EuclideanSpace ℝ (Fin n)) 1,
        0 ≤ @inner ℝ _ _ x (v x))
    (x : EuclideanSpace ℝ (Fin n))
    (hx : x ∈ Metric.closedBall (0 : EuclideanSpace ℝ (Fin n)) 1) :
    ‖x + ((Real.sqrt ((@inner ℝ _ _ x (v x))^2 + ‖v x‖^2 * (1 - ‖x‖^2))
        - @inner ℝ _ _ x (v x)) / ‖v x‖^2) • v x‖ = 1  := by
  have h_sq := ray_param_norm_sq_eq_one hn hvcont hvne hvinner x hx
  have h_nn : 0 ≤ ‖x + ((Real.sqrt ((@inner ℝ _ _ x (v x))^2 + ‖v x‖^2 * (1 - ‖x‖^2))
        - @inner ℝ _ _ x (v x)) / ‖v x‖^2) • v x‖ := norm_nonneg _
  nlinarith [h_sq, h_nn, sq_nonneg (‖x + ((Real.sqrt ((@inner ℝ _ _ x (v x))^2 + ‖v x‖^2
        * (1 - ‖x‖^2)) - @inner ℝ _ _ x (v x)) / ‖v x‖^2) • v x‖ - 1)]

end Problems.Topology.brouwer_fixed_point
