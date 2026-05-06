import Mathlib
import Problems.proj_nonexpansive.Defs

-- variational_ineq: metric projector satisfies inner (P x - x) (y - P x) >= 0 for y in K
-- entry_kind: Backward
open scoped InnerProductSpace

namespace Problems.proj_nonexpansive

theorem variational_ineq :
    ∀ {X : Type*} [NormedAddCommGroup X] [InnerProductSpace ℝ X]
    {K : Set X}, IsClosed K → Convex ℝ K → K.Nonempty →
    ∀ {P : X → X}, IsMetricProjector K P →
    ∀ x, ∀ y ∈ K, ⟪P x - x, y - P x⟫_ℝ ≥ 0 := by sorry

end Problems.proj_nonexpansive
