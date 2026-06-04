import Mathlib
import Problems.Minif2f.amc12a_2009_p5.Defs

namespace Problems.Minif2f.amc12a_2009_p5

-- Direct: (x+1)(x-1)x = x^3 - x via ring, so h₀ collapses to x = 5; then x^3 - 125 = (x^2+5x+25)(x-5).
-- linear_combination with coefficient (x^2 + 5x + 25) closes it in one step.
theorem s575 : ∀ (x : ℝ) (h₀ : x ^ 3 - (x + 1) * (x - 1) * x = 5), x ^ 3 = 125  := by
  intro x h₀
  linear_combination (x^2 + 5*x + 25) * h₀

end Problems.Minif2f.amc12a_2009_p5
