-- Reduce `sum.im ≠ 49` to the strictly-stronger bound `sum.im ≤ 48` on the same
-- range (0 < m < 97). The bound is abstract (single inequality, no equality
-- splits) and is closed via `linarith` with the constant 48 < 49 separation.
import Mathlib
import Problems.Minif2f.amc12a_2009_p15.Defs
import Problems.Minif2f.amc12a_2009_p15.proofs._strategy_s9648

namespace Problems.Minif2f.amc12a_2009_p15

def sum_im_neq_49_below_97 := @Problems.Minif2f.amc12a_2009_p15.s9648

end Problems.Minif2f.amc12a_2009_p15
