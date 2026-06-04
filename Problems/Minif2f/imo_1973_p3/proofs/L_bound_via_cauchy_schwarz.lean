import Mathlib
import Problems.Minif2f.imo_1973_p3.Defs

namespace Problems.Minif2f.imo_1973_p3

-- bound_via_cauchy_schwarz: Cauchy-Schwarz gives (a²+b²)(y²+1) ≥ (ay+b)²=(2-y²)²,
-- then 5(2-y²)²≥4(y²+1) when y²≥4 via (5y²-4)(y²-4)≥0.
theorem bound_via_cauchy_schwarz :
  ∀ (a b y : ℝ), 4 ≤ y ^ 2 → a * y + b = 2 - y ^ 2 → 4 / 5 ≤ a ^ 2 + b ^ 2 := by
  intro a b y hy hab
  have hcs : (a ^ 2 + b ^ 2) * (y ^ 2 + 1) ≥ (a * y + b) ^ 2 := by
    nlinarith [sq_nonneg (a - b * y)]
  have heq : (a * y + b) ^ 2 = (2 - y ^ 2) ^ 2 := by rw [hab]
  have hpoly : 5 * (2 - y ^ 2) ^ 2 ≥ 4 * (y ^ 2 + 1) := by
    nlinarith [sq_nonneg (y ^ 2 - 4)]
  nlinarith [sq_nonneg (a ^ 2 + b ^ 2)]

end Problems.Minif2f.imo_1973_p3
