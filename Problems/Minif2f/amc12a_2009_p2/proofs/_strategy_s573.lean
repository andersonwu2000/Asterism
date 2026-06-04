import Mathlib
import Problems.Minif2f.amc12a_2009_p2.Defs

namespace Problems.Minif2f.amc12a_2009_p2

-- Pure rational arithmetic identity: 1 + 1/(1 + 1/2) = 1 + 2/3 = 5/3.
-- Closed directly by `norm_num` — no sub-goals needed (leaf-bypass).
theorem s573 : 1 + 1 / (1 + 1 / (1 + 1)) = (5 : ℚ) / 3  := by norm_num

end Problems.Minif2f.amc12a_2009_p2
