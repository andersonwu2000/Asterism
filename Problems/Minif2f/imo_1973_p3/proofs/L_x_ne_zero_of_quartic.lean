import Mathlib
import Problems.Minif2f.imo_1973_p3.Defs

namespace Problems.Minif2f.imo_1973_p3

-- x_ne_zero_of_quartic: x = 0 forces LHS = 1 ≠ 0, contradiction via simp
theorem x_ne_zero_of_quartic :
  ∀ (a b x : ℝ), x ^ 4 + a * x ^ 3 + b * x ^ 2 + a * x + 1 = 0 → x ≠ 0 := by
  intro a b x h hx
  subst hx
  simp at h

end Problems.Minif2f.imo_1973_p3
