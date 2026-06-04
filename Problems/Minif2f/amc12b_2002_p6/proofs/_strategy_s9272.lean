import Mathlib
import Problems.Minif2f.amc12b_2002_p6.Defs

namespace Problems.Minif2f.amc12b_2002_p6

-- Direct: specialize h₁ at x = 0 to get b = a*b, i.e. b*(a-1) = 0.
-- Since b ≠ 0 (from h₀.2), mul_eq_zero forces a - 1 = 0, hence a = 1.
theorem s9272 : ∀ (a b : ℝ) (h₀ : a ≠ 0 ∧ b ≠ 0) (h₁ : ∀ x, x ^ 2 + a * x + b = (x - a) * (x - b)), a = 1  := by
  intro a b h₀ h₁
  have hb := h₁ 0
  have hne : b ≠ 0 := h₀.2
  have key : b * (a - 1) = 0 := by linarith [hb]
  rcases mul_eq_zero.mp key with h | h
  · exact absurd h hne
  · linarith

end Problems.Minif2f.amc12b_2002_p6
