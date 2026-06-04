import Mathlib
import Problems.Minif2f.mathd_algebra_132.Defs

namespace Problems.Minif2f.mathd_algebra_132

-- Direct leaf: substitute f, g into the composition equality and let nlinarith
-- finish. After rewriting h₂ : f (g x) = g (f x) becomes x^2 + 2 = (x+2)^2,
-- a linear-after-cancellation identity yielding x = -1/2.
theorem s637 : ∀ (x : ℝ) (f g : ℝ → ℝ) (h₀ : ∀ x, f x = x + 2) (h₁ : ∀ x, g x = x ^ 2) (h₂ : f (g x) = g (f x)), x = -1 / 2  := by
  intro x f g h₀ h₁ h₂
  rw [h₀, h₁, h₁, h₀] at h₂
  nlinarith [h₂]

end Problems.Minif2f.mathd_algebra_132
