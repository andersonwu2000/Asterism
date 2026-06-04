import Mathlib
import Problems.Minif2f.amc12a_2008_p2.Defs

namespace Problems.Minif2f.amc12a_2008_p2

-- Direct arithmetic: `1/2 + 2/3 = 7/6`, so `x * (7/6) = 1` forces `x = 6/7`.
-- Single linarith call on the hypothesis closes the goal — no sub-goals needed.
theorem s569 : ∀ (x : ℝ) (h₀ : x * (1 / 2 + 2 / 3) = 1), x = 6 / 7  := by
  intro x h₀
  linarith

end Problems.Minif2f.amc12a_2008_p2
