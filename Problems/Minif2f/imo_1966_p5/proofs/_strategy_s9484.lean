import Mathlib
import Problems.Minif2f.imo_1966_p5.Defs
import Problems.Minif2f.imo_1966_p5.proofs.L_h_x2_zero
import Problems.Minif2f.imo_1966_p5.proofs.L_h_x3_zero

namespace Problems.Minif2f.imo_1966_p5

-- Decompose `x 1 = 1/|a₁-a₄|` via x 2 = 0 and x 3 = 0; then read off h₁₂.
-- Sub-goals: `h_x2_zero` (x 2 = 0) and `h_x3_zero` (x 3 = 0); both inherit full parent signature.
-- Combinator: substitute zeros into h₁₂, rewrite |a₄-a₁| = |a₁-a₄| via abs_sub_comm, divide.
theorem s9484 : ∀ (x a : ℕ → ℝ) (h₀ : a 1 ≠ a 2) (h₁ : a 1 ≠ a 3) (h₂ : a 1 ≠ a 4) (h₃ : a 2 ≠ a 3) (h₄ : a 2 ≠ a 4) (h₅ : a 3 ≠ a 4) (h₆ : a 1 > a 2) (h₇ : a 2 > a 3) (h₈ : a 3 > a 4) (h₉ : abs (a 1 - a 2) * x 2 + abs (a 1 - a 3) * x 3 + abs (a 1 - a 4) * x 4 = 1) (h₁₀ : abs (a 2 - a 1) * x 1 + abs (a 2 - a 3) * x 3 + abs (a 2 - a 4) * x 4 = 1) (h₁₁ : abs (a 3 - a 1) * x 1 + abs (a 3 - a 2) * x 2 + abs (a 3 - a 4) * x 4 = 1) (h₁₂ : abs (a 4 - a 1) * x 1 + abs (a 4 - a 2) * x 2 + abs (a 4 - a 3) * x 3 = 1), x 1 = 1 / abs (a 1 - a 4)  := by
  intro x a h₀ h₁ h₂ h₃ h₄ h₅ h₆ h₇ h₈ h₉ h₁₀ h₁₁ h₁₂
  have h_x2 : x 2 = 0 := h_x2_zero x a h₀ h₁ h₂ h₃ h₄ h₅ h₆ h₇ h₈ h₉ h₁₀ h₁₁ h₁₂
  have h_x3 : x 3 = 0 := h_x3_zero x a h₀ h₁ h₂ h₃ h₄ h₅ h₆ h₇ h₈ h₉ h₁₀ h₁₁ h₁₂
  rw [h_x2, h_x3, mul_zero, mul_zero, add_zero, add_zero] at h₁₂
  have h_abs_ne : abs (a 1 - a 4) ≠ 0 := ne_of_gt (abs_pos.mpr (by linarith))
  rw [abs_sub_comm (a 4) (a 1)] at h₁₂
  rw [eq_div_iff h_abs_ne]
  linarith

end Problems.Minif2f.imo_1966_p5
