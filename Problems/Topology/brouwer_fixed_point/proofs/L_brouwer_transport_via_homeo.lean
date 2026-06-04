import Mathlib
import Problems.Topology.brouwer_fixed_point.Defs

namespace Problems.Topology.brouwer_fixed_point

-- entry_kind: Backward
theorem brouwer_transport_via_homeo
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E]
    [FiniteDimensional ℝ E] {K : Set E} {n : ℕ}
    (φ : K ≃ₜ Metric.closedBall (0 : EuclideanSpace ℝ (Fin n)) 1)
    {f : E → E} (hcont : ContinuousOn f K) (hmaps : Set.MapsTo f K K) :
    ∃ x ∈ K, f x = x := by sorry

end Problems.Topology.brouwer_fixed_point
