import Mathlib
import Problems.Minif2f.mathd_algebra_28.Defs

namespace Problems.Minif2f.mathd_algebra_28

-- Direct: from ∃ x, 2x²+5x+c ≤ 0, complete the square via (4x+5)² ≥ 0 to get c ≤ 25/8.
theorem s658 : ∀ (c : ℝ) (f : ℝ → ℝ) (h₀ : ∀ x, f x = 2 * x ^ 2 + 5 * x + c) (h₁ : ∃ x, f x ≤ 0), c ≤ 25 / 8  := by
  intro c f h₀ h₁
  obtain ⟨x, hx⟩ := h₁
  have hfx := h₀ x
  rw [hfx] at hx
  nlinarith [sq_nonneg (4*x + 5)]

end Problems.Minif2f.mathd_algebra_28
