import Mathlib
import Problems.inner_zero_iff_smul.Defs

namespace Problems.inner_zero_iff_smul

theorem s161_sub_2 : ∀ {X : Type*} [NormedAddCommGroup X] [InnerProductSpace ℝ X]
    (x y : X),
    inner ℝ x y = 0 → ∀ α : ℝ, ‖x + α • y‖ = ‖x - α • y‖ := by
  intro X _ _ x y h α
  have hxy : inner ℝ x (α • y) = (0 : ℝ) := by
    rw [inner_smul_right, h, mul_zero]
  have hsq : ‖x + α • y‖ ^ 2 = ‖x - α • y‖ ^ 2 := by
    have h1 := norm_add_sq_real x (α • y)
    have h2 := norm_sub_sq_real x (α • y)
    linarith
  have key : Real.sqrt (‖x + α • y‖ ^ 2) = Real.sqrt (‖x - α • y‖ ^ 2) :=
    congr_arg Real.sqrt hsq
  rwa [Real.sqrt_sq (norm_nonneg _), Real.sqrt_sq (norm_nonneg _)] at key

end Problems.inner_zero_iff_smul
