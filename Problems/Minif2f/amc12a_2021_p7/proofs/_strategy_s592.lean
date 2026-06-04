import Mathlib
import Problems.Minif2f.amc12a_2021_p7.Defs

namespace Problems.Minif2f.amc12a_2021_p7

-- Direct proof: (xy - 1)^2 + (x + y)^2 = (x^2 + 1)(y^2 + 1) ≥ 1.
theorem s592 : ∀ (x y : ℝ), 1 ≤ (x * y - 1) ^ 2 + (x + y) ^ 2  := by
  intro x y
  nlinarith [sq_nonneg (x*y - 1), sq_nonneg (x + y), sq_nonneg x, sq_nonneg y,
             sq_nonneg (x*y), sq_nonneg (x - y)]

end Problems.Minif2f.amc12a_2021_p7
