-- Direct proof (leaf-bypass): from `(8/7)^x = 7^7` and `x = logb b (7^7)`,
-- show `b ≠ 1` and `x ≠ 0`, derive `b^x = 7^7` via `Real.rpow_logb`, then
-- equate `(8/7)^x = b^x`, take `Real.log`, cancel `x`, and close via
-- `Real.log_injOn_pos`.
import Mathlib
import Problems.Minif2f.amc12a_2010_p11.Defs
import Problems.Minif2f.amc12a_2010_p11.proofs._strategy_s9401

namespace Problems.Minif2f.amc12a_2010_p11

def b_eq_eight_seventh := @Problems.Minif2f.amc12a_2010_p11.s9401

end Problems.Minif2f.amc12a_2010_p11
