import Mathlib
import Problems.Minif2f.mathd_algebra_214.Defs

namespace Problems.Minif2f.mathd_algebra_214

-- Direct: substitute f via h₀ at x=4 and x=6, then linarith on the two linear equations in a.
theorem s650 : ∀ (a : ℝ) (f : ℝ → ℝ) (h₀ : ∀ x, f x = a * (x - 2) ^ 2 + 3) (h₁ : f 4 = 4), f 6 = 7  := by
  intro a f h₀ h₁
  have h4 := h₀ 4
  have h6 := h₀ 6
  rw [h4] at h₁
  rw [h6]
  linarith

end Problems.Minif2f.mathd_algebra_214
