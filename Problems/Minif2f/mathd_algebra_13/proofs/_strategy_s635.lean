import Mathlib
import Problems.Minif2f.mathd_algebra_13.Defs
import Problems.Minif2f.mathd_algebra_13.proofs.L_eqn_x4
import Problems.Minif2f.mathd_algebra_13.proofs.L_eqn_x6

namespace Problems.Minif2f.mathd_algebra_13

-- Plug x = 4 and x = 6 into the partial-fraction hypothesis h₀ to get
-- two linear constraints on a, b: (a - b = -16) and (a + 3*b = 24).
-- Sub-goals isolate the rational-arithmetic simplification; the combinator is linarith.
theorem s635 : ∀ (a b : ℝ) (h₀ : ∀ x, x - 3 ≠ 0 ∧ x - 5 ≠ 0 → 4 * x / (x ^ 2 - 8 * x + 15) = a / (x - 3) + b / (x - 5)), a = -6 ∧ b = 10  := by
  intro a b h₀
  have h_eqn_x4 := eqn_x4 a b h₀
  have h_eqn_x6 := eqn_x6 a b h₀
  refine ⟨?_, ?_⟩
  · linarith
  · linarith

end Problems.Minif2f.mathd_algebra_13
