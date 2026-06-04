-- Chain anti-period-5 twice: x(n+10) = x((n+5)+5) = -x(n+5) = -(-x n) = x n.
-- Single sub-goal `anti_period_5` (≥1, x(m+5) = -x m) — strictly simpler (2 unfoldings vs 10);
-- closer instantiates it at n and n+5 then `linarith`.
import Mathlib
import Problems.Minif2f.aimeII_2001_p3.Defs
import Problems.Minif2f.aimeII_2001_p3.proofs._strategy_s9339

namespace Problems.Minif2f.aimeII_2001_p3

def periodicity_10 := @Problems.Minif2f.aimeII_2001_p3.s9339

end Problems.Minif2f.aimeII_2001_p3
