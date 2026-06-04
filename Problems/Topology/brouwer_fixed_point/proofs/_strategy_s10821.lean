import Mathlib
import Problems.Topology.brouwer_fixed_point.Defs
import Problems.Topology.brouwer_fixed_point.proofs.L_ray_param_continuous
import Problems.Topology.brouwer_fixed_point.proofs.L_ray_param_norm_eq_one
import Problems.Topology.brouwer_fixed_point.proofs.L_ray_param_zero_on_sphere

namespace Problems.Topology.brouwer_fixed_point

-- Pick the explicit non-negative root of the quadratic ‖x + t · v x‖² = 1:
-- t x := (√(⟨x,vx⟩² + ‖vx‖²·(1-‖x‖²)) - ⟨x,vx⟩) / ‖vx‖².
-- Three sub-goals verify (i) continuity of this formula on closedBall (uses
-- hvcont, hvne), (ii) the formula satisfies ‖x + t·v x‖ = 1 (algebraic, uses
-- hvne to handle division), (iii) on the unit sphere the formula collapses
-- to 0 because 1-‖x‖²=0 and ⟨x,vx⟩ ≥ 0 (hvinner) makes √(⟨x,vx⟩²)=⟨x,vx⟩.
theorem s10821
    {n : ℕ} (hn : 0 < n)
    {v : EuclideanSpace ℝ (Fin n) → EuclideanSpace ℝ (Fin n)}
    (hvcont : ContinuousOn v (Metric.closedBall 0 1))
    (hvne : ∀ x ∈ Metric.closedBall (0 : EuclideanSpace ℝ (Fin n)) 1, v x ≠ 0)
    (hvinner : ∀ x ∈ Metric.sphere (0 : EuclideanSpace ℝ (Fin n)) 1,
        0 ≤ @inner ℝ _ _ x (v x)) :
    ∃ t : EuclideanSpace ℝ (Fin n) → ℝ,
      ContinuousOn t (Metric.closedBall 0 1) ∧
      (∀ x ∈ Metric.closedBall (0 : EuclideanSpace ℝ (Fin n)) 1,
          ‖x + t x • v x‖ = 1) ∧
      (∀ x ∈ Metric.sphere (0 : EuclideanSpace ℝ (Fin n)) 1, t x = 0) := by
  classical
  refine ⟨fun x =>
      (Real.sqrt ((@inner ℝ _ _ x (v x))^2 + ‖v x‖^2 * (1 - ‖x‖^2))
          - @inner ℝ _ _ x (v x)) / ‖v x‖^2,
      ?_, ?_, ?_⟩
  · exact ray_param_continuous hn hvcont hvne hvinner
  · intro x hx
    exact ray_param_norm_eq_one hn hvcont hvne hvinner x hx
  · intro x hx
    exact ray_param_zero_on_sphere hn hvcont hvne hvinner x hx

end Problems.Topology.brouwer_fixed_point
