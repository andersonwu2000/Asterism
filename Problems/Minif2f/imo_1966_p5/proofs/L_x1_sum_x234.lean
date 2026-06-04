import Mathlib
import Problems.Minif2f.imo_1966_p5.Defs

namespace Problems.Minif2f.imo_1966_p5

set_option linter.style.longLine false
set_option linter.unusedVariables false

-- x1_sum_x234: h₉ − h₁₀ factors out (a₁−a₂) > 0 giving (a₁−a₂)·(x₂+x₃+x₄−x₁) = 0,
-- then mul_eq_zero + linarith closes x₁ = x₂ + x₃ + x₄.
theorem x1_sum_x234 : ∀ (x a : ℕ → ℝ) (h₀ : a 1 ≠ a 2) (h₁ : a 1 ≠ a 3) (h₂ : a 1 ≠ a 4) (h₃ : a 2 ≠ a 3) (h₄ : a 2 ≠ a 4) (h₅ : a 3 ≠ a 4) (h₆ : a 1 > a 2) (h₇ : a 2 > a 3) (h₈ : a 3 > a 4) (h₉ : abs (a 1 - a 2) * x 2 + abs (a 1 - a 3) * x 3 + abs (a 1 - a 4) * x 4 = 1) (h₁₀ : abs (a 2 - a 1) * x 1 + abs (a 2 - a 3) * x 3 + abs (a 2 - a 4) * x 4 = 1) (h₁₁ : abs (a 3 - a 1) * x 1 + abs (a 3 - a 2) * x 2 + abs (a 3 - a 4) * x 4 = 1) (h₁₂ : abs (a 4 - a 1) * x 1 + abs (a 4 - a 2) * x 2 + abs (a 4 - a 3) * x 3 = 1), x 1 = x 2 + x 3 + x 4 := by
  intro x a h₀ h₁ h₂ h₃ h₄ h₅ h₆ h₇ h₈ h₉ h₁₀ h₁₁ h₁₂
  have ha12 : a 1 - a 2 > 0 := by linarith
  have ha13 : a 1 - a 3 > 0 := by linarith
  have ha14 : a 1 - a 4 > 0 := by linarith
  have ha23 : a 2 - a 3 > 0 := by linarith
  have ha24 : a 2 - a 4 > 0 := by linarith
  rw [abs_of_pos ha12, abs_of_pos ha13, abs_of_pos ha14] at h₉
  rw [abs_of_neg (by linarith), abs_of_pos ha23, abs_of_pos ha24] at h₁₀
  have key : (a 1 - a 2) * (x 2 + x 3 + x 4 - x 1) = 0 := by linear_combination h₉ - h₁₀
  have hne : a 1 - a 2 ≠ 0 := by linarith
  have hfact := mul_eq_zero.mp key
  cases hfact with
  | inl h => exact absurd h hne
  | inr h => linarith

end Problems.Minif2f.imo_1966_p5
