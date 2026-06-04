import Mathlib
import Problems.Minif2f.amc12a_2008_p8.Defs

namespace Problems.Minif2f.amc12a_2008_p8

-- entry_kind: Builder
theorem x_sq_eq_two : ∀ (x y : ℝ), 0 < x → y = 1 →
    6 * x ^ 2 = 2 * (6 * y ^ 2) → x ^ 2 = 2 := by grind

end Problems.Minif2f.amc12a_2008_p8
