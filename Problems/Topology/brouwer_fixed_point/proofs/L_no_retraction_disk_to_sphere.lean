import Mathlib
import Problems.Topology.brouwer_fixed_point.Defs

namespace Problems.Topology.brouwer_fixed_point

-- entry_kind: Backward
theorem no_retraction_disk_to_sphere
    {n : ℕ} (_hn : 0 < n) :
    ¬ ∃ r : EuclideanSpace ℝ (Fin n) → EuclideanSpace ℝ (Fin n),
      ContinuousOn r (Metric.closedBall 0 1) ∧
      Set.MapsTo r (Metric.closedBall (0 : EuclideanSpace ℝ (Fin n)) 1)
        (Metric.sphere (0 : EuclideanSpace ℝ (Fin n)) 1) ∧
      ∀ x ∈ Metric.sphere (0 : EuclideanSpace ℝ (Fin n)) 1, r x = x := by sorry

end Problems.Topology.brouwer_fixed_point
