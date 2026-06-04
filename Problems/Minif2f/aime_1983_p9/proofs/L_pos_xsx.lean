import Mathlib
import Problems.Minif2f.aime_1983_p9.Defs

namespace Problems.Minif2f.aime_1983_p9

-- pos_xsx: x * sin x is positive for x in (0, π) by positivity of x and sin on that interval
-- Uses Real.sin_pos_of_pos_of_lt_pi and mul_pos.
set_option linter.unusedVariables false in
theorem pos_xsx : ∀ (x : ℝ) (h₀ : 0 < x ∧ x < Real.pi), 0 < x * Real.sin x := by
  intro x ⟨hx_pos, hx_lt_pi⟩
  exact mul_pos hx_pos (Real.sin_pos_of_pos_of_lt_pi hx_pos hx_lt_pi)

end Problems.Minif2f.aime_1983_p9
