import Mathlib
import Problems.Minif2f.mathd_algebra_159.Defs

namespace Problems.Minif2f.mathd_algebra_159

-- Direct: specialize h₀ at x=1 (gives f 1 = -1 - b), rewrite into h₁, linarith.
theorem s643 : ∀ (b : ℝ) (f : ℝ → ℝ) (h₀ : ∀ x, f x = 3 * x ^ 4 - 7 * x ^ 3 + 2 * x ^ 2 - b * x + 1) (h₁ : f 1 = 1), b = -2  := by
  intro b f h₀ h₁
  have h := h₀ 1
  rw [h] at h₁
  linarith

end Problems.Minif2f.mathd_algebra_159
