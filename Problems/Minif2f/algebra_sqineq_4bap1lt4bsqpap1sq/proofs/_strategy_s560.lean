import Mathlib
import Problems.Minif2f.algebra_sqineq_4bap1lt4bsqpap1sq.Defs

namespace Problems.Minif2f.algebra_sqineq_4bap1lt4bsqpap1sq

-- Direct: AM-GM-style 2uv ≤ u² + v² with u = 2b, v = a+1.
-- nlinarith closes from sq_nonneg (2b - (a+1)) which expands to (a+1)² + 4b² - 4b(a+1) ≥ 0.
theorem s560 : ∀ (a b : ℝ), 4 * b * (a + 1) ≤ 4 * b ^ 2 + (a + 1) ^ 2  := by
  intro a b
  nlinarith [sq_nonneg (2 * b - (a + 1)), sq_nonneg (2 * b + (a + 1))]

end Problems.Minif2f.algebra_sqineq_4bap1lt4bsqpap1sq
