import Mathlib
import Problems.Minif2f.imo_1966_p5.Defs
import Problems.Minif2f.imo_1966_p5.proofs.L_hx2_is_zero
import Problems.Minif2f.imo_1966_p5.proofs.L_hx3_is_zero

namespace Problems.Minif2f.imo_1966_p5

-- Reduce `x 4 = 1/|a₁-a₄|` to two simpler facts: x 2 = 0 and x 3 = 0.
-- With these, h₉ becomes |a₁-a₄|·x₄ = 1 (after abs unfolding via a₁>a₄),
-- and division yields the goal.
theorem s9428 : ∀ (x a : ℕ → ℝ) (h₀ : a 1 ≠ a 2) (h₁ : a 1 ≠ a 3) (h₂ : a 1 ≠ a 4) (h₃ : a 2 ≠ a 3) (h₄ : a 2 ≠ a 4) (h₅ : a 3 ≠ a 4) (h₆ : a 1 > a 2) (h₇ : a 2 > a 3) (h₈ : a 3 > a 4) (h₉ : abs (a 1 - a 2) * x 2 + abs (a 1 - a 3) * x 3 + abs (a 1 - a 4) * x 4 = 1) (h₁₀ : abs (a 2 - a 1) * x 1 + abs (a 2 - a 3) * x 3 + abs (a 2 - a 4) * x 4 = 1) (h₁₁ : abs (a 3 - a 1) * x 1 + abs (a 3 - a 2) * x 2 + abs (a 3 - a 4) * x 4 = 1) (h₁₂ : abs (a 4 - a 1) * x 1 + abs (a 4 - a 2) * x 2 + abs (a 4 - a 3) * x 3 = 1), x 4 = 1 / abs (a 1 - a 4)  := by
  intro x a h₀ h₁ h₂ h₃ h₄ h₅ h₆ h₇ h₈ h₉ h₁₀ h₁₁ h₁₂
  have hx2 := hx2_is_zero x a h₀ h₁ h₂ h₃ h₄ h₅ h₆ h₇ h₈ h₉ h₁₀ h₁₁ h₁₂
  have hx3 := hx3_is_zero x a h₀ h₁ h₂ h₃ h₄ h₅ h₆ h₇ h₈ h₉ h₁₀ h₁₁ h₁₂
  have ha12 : (0 : ℝ) < a 1 - a 2 := by linarith
  have ha13 : (0 : ℝ) < a 1 - a 3 := by linarith
  have ha14 : (0 : ℝ) < a 1 - a 4 := by linarith
  rw [abs_of_pos ha12, abs_of_pos ha13, abs_of_pos ha14] at h₉
  rw [hx2, hx3] at h₉
  rw [abs_of_pos ha14]
  have hne : a 1 - a 4 ≠ 0 := ne_of_gt ha14
  field_simp
  linarith

end Problems.Minif2f.imo_1966_p5
