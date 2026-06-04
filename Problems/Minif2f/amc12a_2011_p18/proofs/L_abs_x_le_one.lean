import Mathlib
import Problems.Minif2f.amc12a_2011_p18.Defs

namespace Problems.Minif2f.amc12a_2011_p18

-- entry_kind: Builder
theorem abs_x_le_one (x y : ℝ) (h₀ : abs (x + y) + abs (x - y) = 2) : abs x ≤ 1 := by grind

end Problems.Minif2f.amc12a_2011_p18
