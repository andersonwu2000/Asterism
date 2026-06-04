import Mathlib
namespace Problems.Minif2f.imo_1966_p5

-- h_sum_2: x1+x2 = x3+x4 from Eq2-Eq3 after abs-rewrite, factoring out (a2-a3)>0
-- Rewrite abs in h₁₀ and h₁₁ using sign of differences (a1>a2>a3>a4),
-- then linear_combination h₁₁ - h₁₀ yields (a2-a3)*(x1+x2-x3-x4)=0;
-- divide by nonzero (a2-a3) to conclude.
theorem h_sum_2 : ∀ (x a : ℕ → ℝ) (h₀ : a 1 ≠ a 2) (h₁ : a 1 ≠ a 3) (h₂ : a 1 ≠ a 4)
    (h₃ : a 2 ≠ a 3) (h₄ : a 2 ≠ a 4) (h₅ : a 3 ≠ a 4) (h₆ : a 1 > a 2) (h₇ : a 2 > a 3)
    (h₈ : a 3 > a 4) (h₉ : abs (a 1 - a 2) * x 2 + abs (a 1 - a 3) * x 3 +
    abs (a 1 - a 4) * x 4 = 1) (h₁₀ : abs (a 2 - a 1) * x 1 + abs (a 2 - a 3) * x 3 +
    abs (a 2 - a 4) * x 4 = 1) (h₁₁ : abs (a 3 - a 1) * x 1 + abs (a 3 - a 2) * x 2 +
    abs (a 3 - a 4) * x 4 = 1) (h₁₂ : abs (a 4 - a 1) * x 1 + abs (a 4 - a 2) * x 2 +
    abs (a 4 - a 3) * x 3 = 1), x 1 + x 2 = x 3 + x 4 := by
  intro x a h₀ h₁ h₂ h₃ h₄ h₅ h₆ h₇ h₈ h₉ h₁₀ h₁₁ h₁₂
  have ha23 : a 2 - a 3 > 0 := by linarith
  have ha34 : a 3 - a 4 > 0 := by linarith
  have ha13 : a 1 - a 3 > 0 := by linarith
  have ha24 : a 2 - a 4 > 0 := by linarith
  rw [abs_of_neg (by linarith : a 2 - a 1 < 0), abs_of_pos ha23, abs_of_pos ha24] at h₁₀
  rw [abs_of_neg (by linarith : a 3 - a 1 < 0), abs_of_neg (by linarith : a 3 - a 2 < 0),
      abs_of_pos ha34] at h₁₁
  have key : (a 2 - a 3) * (x 1 + x 2 - x 3 - x 4) = 0 := by linear_combination h₁₁ - h₁₀
  have ha23ne : a 2 - a 3 ≠ 0 := by linarith
  rcases mul_eq_zero.mp key with h | h
  · exact absurd h ha23ne
  · linarith

end Problems.Minif2f.imo_1966_p5
