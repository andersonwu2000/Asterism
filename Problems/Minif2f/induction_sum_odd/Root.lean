-- Direct proof: induction on n.
-- Base: empty sum = 0 = 0^2. Step: ∑_{k<n+1} (2k+1) = ∑_{k<n} (2k+1) + (2n+1)
-- = n^2 + 2n + 1 = (n+1)^2 by ring.
import Mathlib
import Problems.Minif2f.induction_sum_odd.Defs
import Problems.Minif2f.induction_sum_odd.proofs._strategy_s629

namespace Problems.Minif2f.induction_sum_odd

def main := @Problems.Minif2f.induction_sum_odd.s629

end Problems.Minif2f.induction_sum_odd
