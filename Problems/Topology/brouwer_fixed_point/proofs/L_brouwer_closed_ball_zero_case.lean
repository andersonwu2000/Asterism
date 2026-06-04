import Mathlib
import Problems.Topology.brouwer_fixed_point.Defs

namespace Problems.Topology.brouwer_fixed_point

-- entry_kind: Builder
-- brouwer_closed_ball_zero_case: n=0 case is trivial; EuclideanSpace ℝ (Fin 0) is
-- a subsingleton so the closed ball subtype is also a subsingleton, forcing g y = y.
theorem brouwer_closed_ball_zero_case
    (g : Metric.closedBall (0 : EuclideanSpace ℝ (Fin 0)) 1 →
         Metric.closedBall (0 : EuclideanSpace ℝ (Fin 0)) 1)
    (_hcont : Continuous g) :
    ∃ y, g y = y := by
  refine ⟨⟨0, by simp⟩, Subsingleton.elim _ _⟩

end Problems.Topology.brouwer_fixed_point
