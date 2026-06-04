-- Direct induction on k: base case k=0 reduces 2*0+1=1 to h₀; succ step applies
-- h₂ at n=2(k+1)+1 (odd, >1) to rewrite f(2k+3) = f(2k+1)+2, then uses ih.
import Mathlib
import Problems.Minif2f.amc12a_2017_p7.Defs
import Problems.Minif2f.amc12a_2017_p7.proofs._strategy_s9267

namespace Problems.Minif2f.amc12a_2017_p7

def odd_value := @Problems.Minif2f.amc12a_2017_p7.s9267

end Problems.Minif2f.amc12a_2017_p7
