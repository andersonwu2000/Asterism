import Mathlib
import Problems.Minif2f.imo_1973_p3.Defs

namespace Problems.Minif2f.imo_1973_p3

-- y_sq_ge_four: AM-GM identity (x+1/x)^2 = (x-1/x)^2 + 4 ≥ 4 for x ≠ 0
theorem y_sq_ge_four :
  ∀ (x : ℝ), x ≠ 0 → 4 ≤ (x + 1/x) ^ 2 := by
  intro x hx
  have h : (x + 1/x)^2 = (x - 1/x)^2 + 4 := by field_simp; ring
  linarith [sq_nonneg (x - 1/x)]

end Problems.Minif2f.imo_1973_p3
