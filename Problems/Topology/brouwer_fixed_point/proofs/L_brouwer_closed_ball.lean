import Mathlib
import Problems.Topology.brouwer_fixed_point.Defs

namespace Problems.Topology.brouwer_fixed_point

-- entry_kind: Backward
theorem brouwer_closed_ball
    {n : ℕ} (g : Metric.closedBall (0 : EuclideanSpace ℝ (Fin n)) 1 →
                  Metric.closedBall (0 : EuclideanSpace ℝ (Fin n)) 1)
    (_hcont : Continuous g) :
    ∃ y, g y = y := by sorry

end Problems.Topology.brouwer_fixed_point
