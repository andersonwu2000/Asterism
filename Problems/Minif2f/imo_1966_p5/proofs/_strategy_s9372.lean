import Mathlib
import Problems.Minif2f.imo_1966_p5.Defs
import Problems.Minif2f.imo_1966_p5.proofs.L_abs_a1_sub_a4
import Problems.Minif2f.imo_1966_p5.proofs.L_x1_eq_inv_unsigned

namespace Problems.Minif2f.imo_1966_p5

-- Decompose `x 1 = 1 / abs (a 1 - a 4)` by removing the `abs` wrapper:
--  · h_unsigned  : x 1 = 1 / (a 1 - a 4) — the linear-system algebra (abs-free).
--  · h_abs       : abs (a 1 - a 4) = a 1 - a 4 — positivity from h₆,h₇,h₈.
-- Combinator: rewrite `abs (a 1 - a 4)` with h_abs, then close by h_unsigned.
theorem s9372 : ∀ (x a : ℕ → ℝ) (h₀ : a 1 ≠ a 2) (h₁ : a 1 ≠ a 3) (h₂ : a 1 ≠ a 4) (h₃ : a 2 ≠ a 3) (h₄ : a 2 ≠ a 4) (h₅ : a 3 ≠ a 4) (h₆ : a 1 > a 2) (h₇ : a 2 > a 3) (h₈ : a 3 > a 4) (h₉ : abs (a 1 - a 2) * x 2 + abs (a 1 - a 3) * x 3 + abs (a 1 - a 4) * x 4 = 1) (h₁₀ : abs (a 2 - a 1) * x 1 + abs (a 2 - a 3) * x 3 + abs (a 2 - a 4) * x 4 = 1) (h₁₁ : abs (a 3 - a 1) * x 1 + abs (a 3 - a 2) * x 2 + abs (a 3 - a 4) * x 4 = 1) (h₁₂ : abs (a 4 - a 1) * x 1 + abs (a 4 - a 2) * x 2 + abs (a 4 - a 3) * x 3 = 1), x 1 = 1 / abs (a 1 - a 4)  := by
  intro x a h₀ h₁ h₂ h₃ h₄ h₅ h₆ h₇ h₈ h₉ h₁₀ h₁₁ h₁₂
  have h_unsigned := x1_eq_inv_unsigned x a h₀ h₁ h₂ h₃ h₄ h₅ h₆ h₇ h₈ h₉ h₁₀ h₁₁ h₁₂
  have h_abs := abs_a1_sub_a4 x a h₀ h₁ h₂ h₃ h₄ h₅ h₆ h₇ h₈ h₉ h₁₀ h₁₁ h₁₂
  rw [h_abs]
  exact h_unsigned

end Problems.Minif2f.imo_1966_p5
