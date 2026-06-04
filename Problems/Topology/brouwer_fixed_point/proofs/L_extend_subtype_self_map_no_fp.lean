import Mathlib
import Problems.Topology.brouwer_fixed_point.Defs

namespace Problems.Topology.brouwer_fixed_point

-- entry_kind: Backward
theorem extend_subtype_self_map_no_fp
    {n : ℕ} (_hn : 0 < n)
    (g : Metric.closedBall (0 : EuclideanSpace ℝ (Fin n)) 1 →
         Metric.closedBall (0 : EuclideanSpace ℝ (Fin n)) 1)
    (_hcont : Continuous g)
    (hnofp : ∀ y, g y ≠ y) :
    ∃ f : EuclideanSpace ℝ (Fin n) → EuclideanSpace ℝ (Fin n),
      ContinuousOn f (Metric.closedBall 0 1) ∧
      Set.MapsTo f
        (Metric.closedBall (0 : EuclideanSpace ℝ (Fin n)) 1)
        (Metric.closedBall (0 : EuclideanSpace ℝ (Fin n)) 1) ∧
      ∀ x ∈ Metric.closedBall (0 : EuclideanSpace ℝ (Fin n)) 1, f x ≠ x := by sorry

end Problems.Topology.brouwer_fixed_point
