import Mathlib
import Problems.Minif2f.mathd_algebra_462.Defs

namespace Problems.Minif2f.mathd_algebra_462

-- Closed-form rational arithmetic; `norm_num` evaluates the LHS and discharges equality.
theorem s675 : ((1 : ℚ) / 2 + 1 / 3) * (1 / 2 - 1 / 3) = 5 / 36  := by norm_num

end Problems.Minif2f.mathd_algebra_462
