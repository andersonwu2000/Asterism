-- Reduce complex inequality to real-part inequality: the sub-goal
-- `sum_re_neq_48` shows S(m).re ≠ 48 for any m > 97, while at m = 97 the real
-- part is exactly 48 (closed-form by norm_num via I_sq + pow_succ on the
-- finite Icc sum). Equality of the complex sums would force equality of real
-- parts, contradicting the sub-goal.
import Mathlib
import Problems.Minif2f.amc12a_2009_p15.Defs
import Problems.Minif2f.amc12a_2009_p15.proofs._strategy_s9454

namespace Problems.Minif2f.amc12a_2009_p15

def sum_neq_above_97 := @Problems.Minif2f.amc12a_2009_p15.s9454

end Problems.Minif2f.amc12a_2009_p15
