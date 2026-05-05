import Mathlib
import Problems.inner_zero_iff_smul.Defs

namespace Problems.inner_zero_iff_smul

theorem s161_sub_1 : ∀ {X : Type*} [NormedAddCommGroup X] [InnerProductSpace ℝ X]
    (x y : X) (α : ℝ),
    ‖x + α • y‖ ^ 2 - ‖x - α • y‖ ^ 2 = 4 * α * inner ℝ x y := by
  intro X _ _ x y α
  simp only [norm_add_sq_real, norm_sub_sq_real, inner_smul_right]
  ring

end Problems.inner_zero_iff_smul
