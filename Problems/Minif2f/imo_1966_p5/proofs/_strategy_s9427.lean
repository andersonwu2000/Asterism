import Mathlib
import Problems.Minif2f.imo_1966_p5.Defs
import Problems.Minif2f.imo_1966_p5.proofs.L_h_sum_2
import Problems.Minif2f.imo_1966_p5.proofs.L_h_x1_sum

namespace Problems.Minif2f.imo_1966_p5

-- Decompose `x 2 = 0` into two linear identities derivable from the equation pairs.
-- `h_sum_2`: from Eq2 - Eq3 (factoring out a₂ - a₃ > 0) yields x 1 + x 2 = x 3 + x 4.
-- `h_x1_sum`: from Eq1 - Eq2 (factoring out a₁ - a₂ > 0) yields x 1 = x 2 + x 3 + x 4.
-- Combining: substituting x 1 in `h_sum_2` gives 2·x 2 = 0, closed by `linarith`.
theorem s9427 : ∀ (x a : ℕ → ℝ) (h₀ : a 1 ≠ a 2) (h₁ : a 1 ≠ a 3) (h₂ : a 1 ≠ a 4) (h₃ : a 2 ≠ a 3) (h₄ : a 2 ≠ a 4) (h₅ : a 3 ≠ a 4) (h₆ : a 1 > a 2) (h₇ : a 2 > a 3) (h₈ : a 3 > a 4) (h₉ : abs (a 1 - a 2) * x 2 + abs (a 1 - a 3) * x 3 + abs (a 1 - a 4) * x 4 = 1) (h₁₀ : abs (a 2 - a 1) * x 1 + abs (a 2 - a 3) * x 3 + abs (a 2 - a 4) * x 4 = 1) (h₁₁ : abs (a 3 - a 1) * x 1 + abs (a 3 - a 2) * x 2 + abs (a 3 - a 4) * x 4 = 1) (h₁₂ : abs (a 4 - a 1) * x 1 + abs (a 4 - a 2) * x 2 + abs (a 4 - a 3) * x 3 = 1), x 2 = 0  := by
  intro x a h₀ h₁ h₂ h₃ h₄ h₅ h₆ h₇ h₈ h₉ h₁₀ h₁₁ h₁₂
  have hsum := h_sum_2 x a h₀ h₁ h₂ h₃ h₄ h₅ h₆ h₇ h₈ h₉ h₁₀ h₁₁ h₁₂
  have hx1 := h_x1_sum x a h₀ h₁ h₂ h₃ h₄ h₅ h₆ h₇ h₈ h₉ h₁₀ h₁₁ h₁₂
  linarith

end Problems.Minif2f.imo_1966_p5
