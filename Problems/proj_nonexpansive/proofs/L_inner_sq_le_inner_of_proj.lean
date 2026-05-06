import Mathlib
import Problems.proj_nonexpansive.Defs

namespace Problems.proj_nonexpansive

-- inner_sq_le_inner_of_proj: for a metric projector P onto convex K,
-- ‖P x - P y‖ ^ 2 ≤ inner ℝ (x - y) (P x - P y)
-- Proof: apply projector_variational_ineq at x (test point P y ∈ K) and at y (test point P x ∈ K),
-- add the two inequalities; inner product linearity reduces the sum to ‖P x - P y‖² ≤ inner(x-y, Px-Py).
-- entry_kind: Backward
theorem inner_sq_le_inner_of_proj {X : Type*} [NormedAddCommGroup X] [InnerProductSpace ℝ X]
    {K : Set X} (hconvex : Convex ℝ K) {P : X → X} (hP : IsMetricProjector K P)
    (x y : X) : ‖P x - P y‖ ^ 2 ≤ @inner ℝ _ _ (x - y) (P x - P y) := by sorry

end Problems.proj_nonexpansive
