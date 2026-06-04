import Mathlib
import Problems.Topology.brouwer_fixed_point.Defs

namespace Problems.Topology.brouwer_fixed_point

-- Direct: closed unit ball in `EuclideanSpace ℝ (Fin n)` is convex and
-- contains `0`, hence star-convex at `0`, hence contractible.
-- Closer is `StarConvex.contractibleSpace` applied to `convex_closedBall`.
theorem s10819 (n : ℕ) :
    ContractibleSpace
      (Metric.closedBall (0 : EuclideanSpace ℝ (Fin n)) 1)  := by
  have hconv : Convex ℝ (Metric.closedBall (0 : EuclideanSpace ℝ (Fin n)) 1) :=
    convex_closedBall _ _
  have hmem : (0 : EuclideanSpace ℝ (Fin n)) ∈ Metric.closedBall (0 : EuclideanSpace ℝ (Fin n)) 1 :=
    Metric.mem_closedBall_self (by norm_num)
  exact (hconv.starConvex hmem).contractibleSpace ⟨_, hmem⟩

end Problems.Topology.brouwer_fixed_point
