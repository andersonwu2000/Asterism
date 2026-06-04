import Mathlib
import Problems.Minif2f.algebra_sqineq_36azm9asqle36zsq.Defs

namespace Problems.Minif2f.algebra_sqineq_36azm9asqle36zsq

-- Direct proof: rearrange to `0 ≤ 36z² - 36az + 9a² = (6z - 3a)²`.
-- `nlinarith` closes the goal given `sq_nonneg (6*z - 3*a)` as a hint —
-- the square expansion supplies exactly the cross-term cancellation.
theorem s559 : ∀ (z a : ℝ), 36 * (a * z) - 9 * a ^ 2 ≤ 36 * z ^ 2  := by
  intro z a
  nlinarith [sq_nonneg (6 * z - 3 * a)]

end Problems.Minif2f.algebra_sqineq_36azm9asqle36zsq
