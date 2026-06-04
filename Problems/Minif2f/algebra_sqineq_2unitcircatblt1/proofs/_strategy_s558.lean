import Mathlib
import Problems.Minif2f.algebra_sqineq_2unitcircatblt1.Defs

namespace Problems.Minif2f.algebra_sqineq_2unitcircatblt1

-- Direct AM-GM: 2ab ≤ a²+b² = 2, hence ab ≤ 1; nlinarith closes via (a-b)² ≥ 0.
theorem s558 : ∀ (a b : ℝ) (h₀ : a ^ 2 + b ^ 2 = 2), a * b ≤ 1  := by
  intro a b h₀
  nlinarith [sq_nonneg (a - b), sq_nonneg (a + b), h₀]

end Problems.Minif2f.algebra_sqineq_2unitcircatblt1
