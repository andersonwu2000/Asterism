import Mathlib
import Problems.Minif2f.imo_1966_p5.Defs

namespace Problems.Minif2f.imo_1966_p5

-- h_x4: subtract Eq3 - Eq4 after unfolding abs via ordering; (a3-a4)*(x4-x1-x2-x3)=0
-- with a3-a4 > 0 forces x4 = x1+x2+x3 by nlinarith.
theorem h_x4 : ∀ (x a : ℕ → ℝ) (h₀ : a 1 ≠ a 2) (h₁ : a 1 ≠ a 3) (h₂ : a 1 ≠ a 4)
    (h₃ : a 2 ≠ a 3) (h₄ : a 2 ≠ a 4) (h₅ : a 3 ≠ a 4) (h₆ : a 1 > a 2)
    (h₇ : a 2 > a 3) (h₈ : a 3 > a 4)
    (h₉ : abs (a 1 - a 2) * x 2 + abs (a 1 - a 3) * x 3 + abs (a 1 - a 4) * x 4 = 1)
    (h₁₀ : abs (a 2 - a 1) * x 1 + abs (a 2 - a 3) * x 3 + abs (a 2 - a 4) * x 4 = 1)
    (h₁₁ : abs (a 3 - a 1) * x 1 + abs (a 3 - a 2) * x 2 + abs (a 3 - a 4) * x 4 = 1)
    (h₁₂ : abs (a 4 - a 1) * x 1 + abs (a 4 - a 2) * x 2 + abs (a 4 - a 3) * x 3 = 1),
    x 4 = x 1 + x 2 + x 3 := by
  intro x a _h₀ _h₁ _h₂ _h₃ _h₄ _h₅ h₆ h₇ h₈ _h₉ _h₁₀ h₁₁ h₁₂
  have ha12 : a 1 - a 2 > 0 := by linarith
  have ha13 : a 1 - a 3 > 0 := by linarith
  have ha14 : a 1 - a 4 > 0 := by linarith
  have ha23 : a 2 - a 3 > 0 := by linarith
  have ha24 : a 2 - a 4 > 0 := by linarith
  have ha34 : a 3 - a 4 > 0 := by linarith
  rw [abs_of_neg (by linarith), abs_of_neg (by linarith), abs_of_pos ha34] at h₁₁
  rw [abs_of_neg (by linarith), abs_of_neg (by linarith), abs_of_neg (by linarith)] at h₁₂
  nlinarith [mul_comm (a 3 - a 4) (x 4 - x 1 - x 2 - x 3),
             mul_pos ha34 (show a 3 - a 4 > 0 from ha34)]

end Problems.Minif2f.imo_1966_p5
