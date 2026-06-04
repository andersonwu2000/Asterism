import Mathlib
import Problems.Minif2f.algebra_binomnegdiscrineq_10alt28asqp1.Defs

namespace Problems.Minif2f.algebra_binomnegdiscrineq_10alt28asqp1

-- Direct: 28*a^2 - 10*a + 1 ≥ 0 since discriminant 100 - 112 < 0.
-- nlinarith closes it using (28*a - 5)^2 ≥ 0 ⇒ 784*a^2 - 280*a + 25 ≥ 0.
theorem s554 : ∀ (a : ℝ), 10 * a ≤ 28 * a ^ 2 + 1  := by
  intro a
  nlinarith [sq_nonneg (28 * a - 5), sq_nonneg a, sq_nonneg (a - 5/28)]

end Problems.Minif2f.algebra_binomnegdiscrineq_10alt28asqp1
