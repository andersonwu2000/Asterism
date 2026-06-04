import Mathlib
import Problems.Minif2f.mathd_algebra_616.Defs

namespace Problems.Minif2f.mathd_algebra_616

-- Direct computation: g(1) = 0, then f(0) = 0^3 + 2*0 + 1 = 1.
-- Unfold both definitions via `rw`, finish with `ring`.
theorem s688 : ∀ (f g : ℝ → ℝ) (h₀ : ∀ x, f x = x ^ 3 + 2 * x + 1) (h₁ : ∀ x, g x = x - 1), f (g 1) = 1  := by
  intro f g h₀ h₁
  rw [h₁, h₀]
  ring

end Problems.Minif2f.mathd_algebra_616
