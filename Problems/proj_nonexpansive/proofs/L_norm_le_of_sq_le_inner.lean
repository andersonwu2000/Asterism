import Mathlib
import Problems.proj_nonexpansive.Defs

namespace Problems.proj_nonexpansive

-- norm_le_of_sq_le_inner: if ‖v‖ ^ 2 ≤ inner ℝ u v then ‖v‖ ≤ ‖u‖
-- Proof: Cauchy-Schwarz gives inner ℝ u v ≤ ‖u‖ * ‖v‖, so ‖v‖² ≤ ‖u‖ * ‖v‖;
-- case-split on ‖v‖ = 0 (trivial) vs ‖v‖ > 0 (divide both sides by ‖v‖).
-- entry_kind: Builder
theorem norm_le_of_sq_le_inner {X : Type*} [NormedAddCommGroup X] [InnerProductSpace ℝ X]
    (u v : X) (h : ‖v‖ ^ 2 ≤ @inner ℝ _ _ u v) : ‖v‖ ≤ ‖u‖ := by sorry

end Problems.proj_nonexpansive
