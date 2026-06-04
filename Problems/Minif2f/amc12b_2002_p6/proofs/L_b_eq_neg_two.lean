import Mathlib
import Problems.Minif2f.amc12b_2002_p6.Defs

namespace Problems.Minif2f.amc12b_2002_p6

-- b_eq_neg_two: specialize at 0 and 1 to extract linear equations, conclude b = -2
theorem b_eq_neg_two : ∀ (a b : ℝ) (h₀ : a ≠ 0 ∧ b ≠ 0) (h₁ : ∀ x, x ^ 2 + a * x + b = (x - a) * (x - b)), b = -2 := by
  intro a b ⟨ha0, hb0⟩ h₁
  have h0 : b = a * b := by have := h₁ 0; nlinarith [this]
  have ha : a = 1 := by
    have key : b * (1 - a) = 0 := by nlinarith
    cases mul_eq_zero.mp key with
    | inl h => exact absurd h hb0
    | inr h => linarith
  have h1 : (2 : ℝ) + b = 0 := by
    have := h₁ 1; subst ha; nlinarith [this]
  linarith

end Problems.Minif2f.amc12b_2002_p6
