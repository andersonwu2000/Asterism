import Mathlib
import Problems.proj_nonexpansive.Defs

-- norm_le_of_inner_sq_le: norm-sq bounded by inner product implies norm bound
-- entry_kind: Builder
open scoped InnerProductSpace

namespace Problems.proj_nonexpansive

theorem norm_le_of_inner_sq_le :
    ∀ {X : Type*} [NormedAddCommGroup X] [InnerProductSpace ℝ X]
    (a b : X),
    ‖a‖ ^ 2 ≤ ⟪b, a⟫_ℝ → ‖a‖ ≤ ‖b‖ := by sorry

end Problems.proj_nonexpansive
