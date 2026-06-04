import Mathlib
import Problems.Minif2f.imo_1966_p5.Defs

namespace Problems.Minif2f.imo_1966_p5

-- h_x1_sum: Eq1 - Eq2 factors as (a1-a2)*(x1 - x2 - x3 - x4) = 0; since a1-a2 > 0, x1 = x2+x3+x4
theorem h_x1_sum : ∀ (x a : ℕ → ℝ) (h₀ : a 1 ≠ a 2) (h₁ : a 1 ≠ a 3) (h₂ : a 1 ≠ a 4)
    (h₃ : a 2 ≠ a 3) (h₄ : a 2 ≠ a 4) (h₅ : a 3 ≠ a 4)
    (h₆ : a 1 > a 2) (h₇ : a 2 > a 3) (h₈ : a 3 > a 4)
    (h₉ : abs (a 1 - a 2) * x 2 + abs (a 1 - a 3) * x 3 + abs (a 1 - a 4) * x 4 = 1)
    (h₁₀ : abs (a 2 - a 1) * x 1 + abs (a 2 - a 3) * x 3 + abs (a 2 - a 4) * x 4 = 1)
    (h₁₁ : abs (a 3 - a 1) * x 1 + abs (a 3 - a 2) * x 2 + abs (a 3 - a 4) * x 4 = 1)
    (h₁₂ : abs (a 4 - a 1) * x 1 + abs (a 4 - a 2) * x 2 + abs (a 4 - a 3) * x 3 = 1),
    x 1 = x 2 + x 3 + x 4 := by
  intro x a _h₀ _h₁ _h₂ _h₃ _h₄ _h₅ h₆ h₇ h₈ h₉ h₁₀ _h₁₁ _h₁₂
  have ha12 : a 1 - a 2 > 0 := by linarith
  have ha13 : a 1 - a 3 > 0 := by linarith
  have ha14 : a 1 - a 4 > 0 := by linarith
  have ha23 : a 2 - a 3 > 0 := by linarith
  have ha24 : a 2 - a 4 > 0 := by linarith
  rw [abs_of_pos ha12, abs_of_pos ha13, abs_of_pos ha14] at h₉
  rw [abs_of_neg (by linarith), abs_of_pos ha23, abs_of_pos ha24] at h₁₀
  have key : (a 1 - a 2) * (x 1 - x 2 - x 3 - x 4) = 0 := by linear_combination h₁₀ - h₉
  rcases mul_eq_zero.mp key with h | h
  · linarith
  · linarith

end Problems.Minif2f.imo_1966_p5
