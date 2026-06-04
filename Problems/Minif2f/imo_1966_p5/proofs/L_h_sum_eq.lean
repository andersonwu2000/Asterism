import Mathlib
import Problems.Minif2f.imo_1966_p5.Defs

namespace Problems.Minif2f.imo_1966_p5

-- h_sum_eq: subtract Eq2 − Eq3 (h₁₀ − h₁₁), rewrite abs via ordering, factor out (a₂−a₃) > 0
theorem h_sum_eq : ∀ (x a : ℕ → ℝ) (h₀ : a 1 ≠ a 2) (h₁ : a 1 ≠ a 3) (h₂ : a 1 ≠ a 4)
    (h₃ : a 2 ≠ a 3) (h₄ : a 2 ≠ a 4) (h₅ : a 3 ≠ a 4) (h₆ : a 1 > a 2) (h₇ : a 2 > a 3)
    (h₈ : a 3 > a 4)
    (h₉ : abs (a 1 - a 2) * x 2 + abs (a 1 - a 3) * x 3 + abs (a 1 - a 4) * x 4 = 1)
    (h₁₀ : abs (a 2 - a 1) * x 1 + abs (a 2 - a 3) * x 3 + abs (a 2 - a 4) * x 4 = 1)
    (h₁₁ : abs (a 3 - a 1) * x 1 + abs (a 3 - a 2) * x 2 + abs (a 3 - a 4) * x 4 = 1)
    (h₁₂ : abs (a 4 - a 1) * x 1 + abs (a 4 - a 2) * x 2 + abs (a 4 - a 3) * x 3 = 1),
    x 1 + x 2 = x 3 + x 4 := by
  intro x a _ _ _ _ _ _ h₆ h₇ h₈ _ h₁₀ h₁₁ _
  have ha23 : a 2 - a 3 > 0 := by linarith
  have ha34 : a 3 - a 4 > 0 := by linarith
  rw [abs_of_neg (by linarith : a 2 - a 1 < 0), abs_of_pos ha23,
      abs_of_pos (by linarith : a 2 - a 4 > 0)] at h₁₀
  rw [abs_of_neg (by linarith : a 3 - a 1 < 0), abs_of_neg (by linarith : a 3 - a 2 < 0),
      abs_of_pos ha34] at h₁₁
  have key : (a 2 - a 3) * (x 3 + x 4 - x 1 - x 2) = 0 := by linear_combination h₁₀ - h₁₁
  rcases mul_eq_zero.mp key with h | h
  · linarith
  · linarith

end Problems.Minif2f.imo_1966_p5
