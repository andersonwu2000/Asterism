import Mathlib
import Problems.Minif2f.mathd_numbertheory_81.Defs

namespace Problems.Minif2f.mathd_numbertheory_81

-- Pure decidable arithmetic: 71 % 3 reduces by kernel computation.
-- No sub-goals — `decide` closes the goal directly.
theorem s746 : 71 % 3 = 2  := by decide

end Problems.Minif2f.mathd_numbertheory_81
