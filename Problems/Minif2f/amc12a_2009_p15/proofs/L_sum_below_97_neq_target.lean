-- Look at imaginary parts: if sum = 48 + 49*I then sum.im = 49. But the imaginary part
-- of the partial sum follows the pattern ±j (j = ⌈m/2⌉), bounded by 48 for m ≤ 96 and
-- only hitting 49 at m = 97. Sub-goal `sum_im_neq_49_below_97` proves sum.im ≠ 49 for
-- m < 97 — a real-valued inequality that avoids reasoning about complex equality.
import Mathlib
import Problems.Minif2f.amc12a_2009_p15.Defs
import Problems.Minif2f.amc12a_2009_p15.proofs._strategy_s9592

namespace Problems.Minif2f.amc12a_2009_p15

def sum_below_97_neq_target := @Problems.Minif2f.amc12a_2009_p15.s9592

end Problems.Minif2f.amc12a_2009_p15
