import Mathlib
import Problems.inner_zero_iff_smul.Defs

namespace Problems.inner_zero_iff_smul

theorem s161_sub_3 : ∀ {X : Type*} [NormedAddCommGroup X] [InnerProductSpace ℝ X]
    (x y : X),
    (∀ α : ℝ, ‖x + α • y‖ = ‖x - α • y‖) → inner ℝ x y = 0 := by
  intro X _ _ x y h
  have h1 : ‖x + y‖ = ‖x - y‖ := by
    have := h 1
    simp only [one_smul] at this
    exact this
  have key1 : ‖x + y‖ ^ 2 = ‖x - y‖ ^ 2 := by rw [h1]
  rw [norm_add_sq_real, norm_sub_sq_real] at key1
  linarith

end Problems.inner_zero_iff_smul
