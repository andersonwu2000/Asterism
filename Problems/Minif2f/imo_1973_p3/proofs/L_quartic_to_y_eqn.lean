import Mathlib
import Problems.Minif2f.imo_1973_p3.Defs

namespace Problems.Minif2f.imo_1973_p3

-- entry_kind: Builder
theorem quartic_to_y_eqn :
  ∀ (a b x : ℝ), x ≠ 0 → x ^ 4 + a * x ^ 3 + b * x ^ 2 + a * x + 1 = 0 →
    a * (x + 1/x) + b = 2 - (x + 1/x) ^ 2 := by grind

end Problems.Minif2f.imo_1973_p3
