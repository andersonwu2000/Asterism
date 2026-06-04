import Mathlib
import Problems.Minif2f.imo_1966_p5.Defs

namespace Problems.Minif2f.imo_1966_p5

-- h_x4_eq_sum_123: Eq3−Eq4 factors as (a₃−a₄)·(x₄−x₁−x₂−x₃)=0; nonzero scalar gives x₄=x₁+x₂+x₃
theorem h_x4_eq_sum_123 : ∀ (x a : ℕ → ℝ) (h₀ : a 1 ≠ a 2) (h₁ : a 1 ≠ a 3)
    (h₂ : a 1 ≠ a 4) (h₃ : a 2 ≠ a 3) (h₄ : a 2 ≠ a 4) (h₅ : a 3 ≠ a 4)
    (h₆ : a 1 > a 2) (h₇ : a 2 > a 3) (h₈ : a 3 > a 4)
    (h₉ : abs (a 1 - a 2) * x 2 + abs (a 1 - a 3) * x 3 + abs (a 1 - a 4) * x 4 = 1)
    (h₁₀ : abs (a 2 - a 1) * x 1 + abs (a 2 - a 3) * x 3 + abs (a 2 - a 4) * x 4 = 1)
    (h₁₁ : abs (a 3 - a 1) * x 1 + abs (a 3 - a 2) * x 2 + abs (a 3 - a 4) * x 4 = 1)
    (h₁₂ : abs (a 4 - a 1) * x 1 + abs (a 4 - a 2) * x 2 + abs (a 4 - a 3) * x 3 = 1),
    x 4 = x 1 + x 2 + x 3 := by
  intro x a _h₀ _h₁ _h₂ _h₃ _h₄ _h₅ _h₆ _h₇ _h₈ _h₉ _h₁₀ h₁₁ h₁₂
  have ha34 : a 3 - a 4 > 0 := by linarith
  rw [abs_of_neg (by linarith : a 3 - a 1 < 0), abs_of_neg (by linarith : a 3 - a 2 < 0),
      abs_of_pos ha34] at h₁₁
  rw [abs_of_neg (by linarith : a 4 - a 1 < 0), abs_of_neg (by linarith : a 4 - a 2 < 0),
      abs_of_neg (by linarith : a 4 - a 3 < 0)] at h₁₂
  have key : (a 3 - a 4) * (x 4 - x 1 - x 2 - x 3) = 0 := by linear_combination h₁₁ - h₁₂
  rcases mul_eq_zero.mp key with h | h
  · linarith
  · linarith

end Problems.Minif2f.imo_1966_p5
