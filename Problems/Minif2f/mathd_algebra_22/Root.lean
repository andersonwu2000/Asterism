-- Direct proof. Rewrite 5^4 = (5^2)^2, then `Real.logb_pow` pulls the
-- exponent 2 out as a factor, and `Real.logb_self_eq_one` reduces the
-- remaining `logb (5^2) (5^2)` to 1; `norm_num` closes the arithmetic.
import Mathlib
import Problems.Minif2f.mathd_algebra_22.Defs
import Problems.Minif2f.mathd_algebra_22.proofs._strategy_s9302

namespace Problems.Minif2f.mathd_algebra_22

def main := @Problems.Minif2f.mathd_algebra_22.s9302

end Problems.Minif2f.mathd_algebra_22
