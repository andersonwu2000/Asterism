import Mathlib
import Problems.proj_nonexpansive.Defs

-- inner_sq_bound: add variational ineq at x and y to get norm-sq bound on Px-Py
-- entry_kind: Backward
open scoped InnerProductSpace

namespace Problems.proj_nonexpansive

theorem inner_sq_bound :
    ∀ {X : Type*} [NormedAddCommGroup X] [InnerProductSpace ℝ X]
    {K : Set X} {P : X → X},
    (∀ z, P z ∈ K) →
    (∀ z (w : X), w ∈ K → ⟪P z - z, w - P z⟫_ℝ ≥ 0) →
    ∀ x y, ‖P x - P y‖ ^ 2 ≤ ⟪x - y, P x - P y⟫_ℝ := by sorry

end Problems.proj_nonexpansive
