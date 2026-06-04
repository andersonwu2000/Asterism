import Mathlib
import Problems.Minif2f.imo_1966_p5.Defs

namespace Problems.Minif2f.imo_1966_p5

-- h_sum_x12_x34: rewrite abs terms via ordering a₁>a₂>a₃>a₄, nlinarith closes Eq₂-Eq₃
-- After abs_of_pos/abs_of_neg rewrites, nlinarith finds (a₂-a₃)(x₁+x₂-x₃-x₄)=0 via h₁₁-h₁₀.
theorem h_sum_x12_x34 : ∀ (x a : ℕ → ℝ) (h₀ : a 1 ≠ a 2) (h₁ : a 1 ≠ a 3) (h₂ : a 1 ≠ a 4)
    (h₃ : a 2 ≠ a 3) (h₄ : a 2 ≠ a 4) (h₅ : a 3 ≠ a 4)
    (h₆ : a 1 > a 2) (h₇ : a 2 > a 3) (h₈ : a 3 > a 4)
    (h₉ : abs (a 1 - a 2) * x 2 + abs (a 1 - a 3) * x 3 + abs (a 1 - a 4) * x 4 = 1)
    (h₁₀ : abs (a 2 - a 1) * x 1 + abs (a 2 - a 3) * x 3 + abs (a 2 - a 4) * x 4 = 1)
    (h₁₁ : abs (a 3 - a 1) * x 1 + abs (a 3 - a 2) * x 2 + abs (a 3 - a 4) * x 4 = 1)
    (h₁₂ : abs (a 4 - a 1) * x 1 + abs (a 4 - a 2) * x 2 + abs (a 4 - a 3) * x 3 = 1),
    x 1 + x 2 = x 3 + x 4 := by
  intro x a _h₀ _h₁ _h₂ _h₃ _h₄ _h₅ h₆ h₇ h₈ h₉ h₁₀ h₁₁ h₁₂
  have hd12 : a 1 - a 2 > 0 := by linarith
  have hd23 : a 2 - a 3 > 0 := by linarith
  have hd34 : a 3 - a 4 > 0 := by linarith
  have hd13 : a 1 - a 3 > 0 := by linarith
  have hd24 : a 2 - a 4 > 0 := by linarith
  have hd14 : a 1 - a 4 > 0 := by linarith
  rw [abs_of_pos hd12, abs_of_pos hd13, abs_of_pos hd14] at h₉
  rw [abs_of_neg (by linarith), abs_of_pos hd23, abs_of_pos hd24] at h₁₀
  rw [abs_of_neg (by linarith), abs_of_neg (by linarith), abs_of_pos hd34] at h₁₁
  rw [abs_of_neg (by linarith), abs_of_neg (by linarith), abs_of_neg (by linarith)] at h₁₂
  nlinarith

end Problems.Minif2f.imo_1966_p5
