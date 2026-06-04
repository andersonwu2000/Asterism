-- Pointwise bound `1 - k*x ≤ |k*x - 1|` summed over Icc 1 84, plus a closed-form
-- evaluation of `∑ (1 - k*x) = 84 - 3570*x`. Linarith chains the two.
import Mathlib
import Problems.Minif2f.amc12a_2010_p22.Defs
import Problems.Minif2f.amc12a_2010_p22.proofs._strategy_s9460

namespace Problems.Minif2f.amc12a_2010_p22

def sum_lower_half_bound := @Problems.Minif2f.amc12a_2010_p22.s9460

end Problems.Minif2f.amc12a_2010_p22
