import Mathlib
import Problems.Minif2f.imo_1966_p5.Defs
import Problems.Minif2f.imo_1966_p5.proofs.L_x1_plus_x2_eq_x3_plus_x4
import Problems.Minif2f.imo_1966_p5.proofs.L_x1_sum_x234

namespace Problems.Minif2f.imo_1966_p5

-- Decompose `x 2 = 0` into two abs-free linear identities derivable from the four equations.
-- `x1_sum_x234`: from h₉ - h₁₀ (factor out a₁-a₂ > 0) yields x 1 = x 2 + x 3 + x 4.
-- `x1_plus_x2_eq_x3_plus_x4`: from h₁₁ - h₁₀ (factor out a₂-a₃ > 0) yields x 1 + x 2 = x 3 + x 4.
-- Substituting the first into the second gives 2·x 2 = 0; `linarith` closes the goal.
theorem s9485 : ∀ (x a : ℕ → ℝ) (h₀ : a 1 ≠ a 2) (h₁ : a 1 ≠ a 3) (h₂ : a 1 ≠ a 4) (h₃ : a 2 ≠ a 3) (h₄ : a 2 ≠ a 4) (h₅ : a 3 ≠ a 4) (h₆ : a 1 > a 2) (h₇ : a 2 > a 3) (h₈ : a 3 > a 4) (h₉ : abs (a 1 - a 2) * x 2 + abs (a 1 - a 3) * x 3 + abs (a 1 - a 4) * x 4 = 1) (h₁₀ : abs (a 2 - a 1) * x 1 + abs (a 2 - a 3) * x 3 + abs (a 2 - a 4) * x 4 = 1) (h₁₁ : abs (a 3 - a 1) * x 1 + abs (a 3 - a 2) * x 2 + abs (a 3 - a 4) * x 4 = 1) (h₁₂ : abs (a 4 - a 1) * x 1 + abs (a 4 - a 2) * x 2 + abs (a 4 - a 3) * x 3 = 1), x 2 = 0  := by
  intro x a h₀ h₁ h₂ h₃ h₄ h₅ h₆ h₇ h₈ h₉ h₁₀ h₁₁ h₁₂
  have hsum1 := x1_sum_x234 x a h₀ h₁ h₂ h₃ h₄ h₅ h₆ h₇ h₈ h₉ h₁₀ h₁₁ h₁₂
  have hsum2 := x1_plus_x2_eq_x3_plus_x4 x a h₀ h₁ h₂ h₃ h₄ h₅ h₆ h₇ h₈ h₉ h₁₀ h₁₁ h₁₂
  linarith

end Problems.Minif2f.imo_1966_p5
