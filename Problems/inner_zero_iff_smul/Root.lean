import Mathlib
import Problems.inner_zero_iff_smul.Defs

namespace Problems.inner_zero_iff_smul

theorem main : ∀ {X : Type*} [NormedAddCommGroup X] [InnerProductSpace ℝ X] (x y : X),
  inner ℝ x y = 0 ↔ ∀ α : ℝ, ‖x + α • y‖ = ‖x - α • y‖ := by sorry

end Problems.inner_zero_iff_smul
