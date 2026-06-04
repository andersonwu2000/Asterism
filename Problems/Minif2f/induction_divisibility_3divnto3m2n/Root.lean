-- Direct induction on n; succ case factors (k+1)^3 + 2(k+1) = (k^3+2k) + 3(k^2+k+1).
-- Both summands divisible by 3 (ih + explicit factor).
import Mathlib
import Problems.Minif2f.induction_divisibility_3divnto3m2n.Defs
import Problems.Minif2f.induction_divisibility_3divnto3m2n.proofs._strategy_s623

namespace Problems.Minif2f.induction_divisibility_3divnto3m2n

def main := @Problems.Minif2f.induction_divisibility_3divnto3m2n.s623

end Problems.Minif2f.induction_divisibility_3divnto3m2n
