import Mathlib
import Problems.Topology.brouwer_fixed_point.Defs

namespace Problems.Topology.brouwer_fixed_point

-- Direct continuity proof: ‖v x‖^2 ≠ 0 from hvne lets us apply `ContinuousOn.div`;
-- numerator decomposes via sqrt/sub/add/mul on continuous building blocks (id, hvcont,
-- their inner product, and norm-squared).
theorem s10822
    {n : ℕ} (hn : 0 < n)
    {v : EuclideanSpace ℝ (Fin n) → EuclideanSpace ℝ (Fin n)}
    (hvcont : ContinuousOn v (Metric.closedBall 0 1))
    (hvne : ∀ x ∈ Metric.closedBall (0 : EuclideanSpace ℝ (Fin n)) 1, v x ≠ 0)
    (hvinner : ∀ x ∈ Metric.sphere (0 : EuclideanSpace ℝ (Fin n)) 1,
        0 ≤ @inner ℝ _ _ x (v x)) :
    ContinuousOn (fun x : EuclideanSpace ℝ (Fin n) =>
        (Real.sqrt ((@inner ℝ _ _ x (v x))^2 + ‖v x‖^2 * (1 - ‖x‖^2))
            - @inner ℝ _ _ x (v x)) / ‖v x‖^2)
        (Metric.closedBall 0 1)  := by
  have hvne2 : ∀ x ∈ Metric.closedBall (0 : EuclideanSpace ℝ (Fin n)) 1, ‖v x‖^2 ≠ 0 := by
    intro x hx
    exact pow_ne_zero _ (norm_ne_zero_iff.mpr (hvne x hx))
  have hinner : ContinuousOn (fun x : EuclideanSpace ℝ (Fin n) => @inner ℝ _ _ x (v x))
      (Metric.closedBall 0 1) :=
    continuousOn_id.inner hvcont
  have hnormx : ContinuousOn (fun x : EuclideanSpace ℝ (Fin n) => ‖x‖^2)
      (Metric.closedBall 0 1) := by fun_prop
  have hnormv : ContinuousOn (fun x : EuclideanSpace ℝ (Fin n) => ‖v x‖^2)
      (Metric.closedBall 0 1) := hvcont.norm.pow 2
  refine ContinuousOn.div ?_ hnormv hvne2
  refine ContinuousOn.sub ?_ hinner
  refine ContinuousOn.sqrt ?_
  refine (hinner.pow 2).add ?_
  refine hnormv.mul ?_
  exact (continuousOn_const).sub hnormx

end Problems.Topology.brouwer_fixed_point
