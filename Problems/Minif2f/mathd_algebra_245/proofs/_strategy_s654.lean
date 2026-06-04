import Mathlib
import Problems.Minif2f.mathd_algebra_245.Defs

namespace Problems.Minif2f.mathd_algebra_245

-- Direct algebraic identity over ℝ with x ≠ 0; no decomposition needed.
-- `field_simp` uses h₀ to clear all denominators, reducing the goal to a
-- polynomial identity in x which `ring` closes.
-- LHS simplifies to (x/4) * (9 x^4) * (8 x^3) = 72 x^8 / 4 = 18 x^8 = RHS.
theorem s654 : ∀ (x : ℝ) (h₀ : x ≠ 0), (4 / x)⁻¹ * (3 * x ^ 3 / x) ^ 2 * (1 / (2 * x))⁻¹ ^ 3 = 18 * x ^ 8  := by
  intro x h₀
  field_simp
  ring

end Problems.Minif2f.mathd_algebra_245
