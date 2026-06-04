-- Chain anti-period-5 twice: x(n+10) = x((n+5)+5) = -x(n+5) = -(-x n) = x n.
-- anti_period_5 inlined (2 unfoldings of h₆ at n+5 and n+4); outer chain then
-- linarith closes the parent.
import Mathlib
import Problems.Minif2f.aimeII_2001_p3.Defs
import Problems.Minif2f.aimeII_2001_p3.proofs._strategy_s9399

namespace Problems.Minif2f.aimeII_2001_p3

def x_period_10 := @Problems.Minif2f.aimeII_2001_p3.s9399

end Problems.Minif2f.aimeII_2001_p3
