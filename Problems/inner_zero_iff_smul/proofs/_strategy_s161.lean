import Mathlib
import Problems.inner_zero_iff_smul.Defs
import Problems.inner_zero_iff_smul.proofs.L_s161_sub_1
import Problems.inner_zero_iff_smul.proofs.L_s161_sub_2
import Problems.inner_zero_iff_smul.proofs.L_s161_sub_3

namespace Problems.inner_zero_iff_smul

theorem s161 : ∀ {X : Type*} [NormedAddCommGroup X] [InnerProductSpace ℝ X] (x y : X),
  inner ℝ x y = 0 ↔ ∀ α : ℝ, ‖x + α • y‖ = ‖x - α • y‖  := by
  intro X _ _ x y
  exact ⟨s161_sub_2 x y, s161_sub_3 x y⟩

end Problems.inner_zero_iff_smul
