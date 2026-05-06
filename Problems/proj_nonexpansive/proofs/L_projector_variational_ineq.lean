import Mathlib
import Problems.proj_nonexpansive.Defs

namespace Problems.proj_nonexpansive

-- projector_variational_ineq: for a metric projector P onto convex K,
-- for any z ∈ K, 0 ≤ inner ℝ (P x - x) (z - P x)
-- entry_kind: Backward
theorem projector_variational_ineq {X : Type*} [NormedAddCommGroup X] [InnerProductSpace ℝ X]
    {K : Set X} (hconvex : Convex ℝ K) {P : X → X} (hP : IsMetricProjector K P)
    (x z : X) (hz : z ∈ K) : 0 ≤ @inner ℝ _ _ (P x - x) (z - P x) := by sorry

end Problems.proj_nonexpansive
