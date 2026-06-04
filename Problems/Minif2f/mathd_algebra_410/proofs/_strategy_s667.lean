import Mathlib
import Problems.Minif2f.mathd_algebra_410.Defs

namespace Problems.Minif2f.mathd_algebra_410

-- Direct: y = x^2 - 6x + 13 = (x-3)^2 + 4, so y ≥ 4 follows from (x-3)^2 ≥ 0.
-- Rewrite y via h₀, then nlinarith closes with sq_nonneg (x - 3) as a hint.
theorem s667 : ∀ (x y : ℝ) (h₀ : y = x ^ 2 - 6 * x + 13), 4 ≤ y  := by
  intro x y h₀
  rw [h₀]
  nlinarith [sq_nonneg (x - 3)]

end Problems.Minif2f.mathd_algebra_410
