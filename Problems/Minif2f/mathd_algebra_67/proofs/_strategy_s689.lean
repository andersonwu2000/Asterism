import Mathlib
import Problems.Minif2f.mathd_algebra_67.Defs

namespace Problems.Minif2f.mathd_algebra_67

-- Direct computation: substitute both definitions, then evaluate.
-- f(-1) = 5*(-1) + 3 = -2, so g(f(-1)) = g(-2) = (-2)^2 - 2 = 2. `norm_num` closes after rewrites.
theorem s689 : ∀ (f g : ℝ → ℝ) (h₀ : ∀ x, f x = 5 * x + 3) (h₁ : ∀ x, g x = x ^ 2 - 2), g (f (-1)) = 2  := by
  intro f g h₀ h₁
  rw [h₁, h₀]
  norm_num

end Problems.Minif2f.mathd_algebra_67
