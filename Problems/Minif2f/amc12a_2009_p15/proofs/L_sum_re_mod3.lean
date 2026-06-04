-- Reduce to a single closed-form lemma indexed by n ∈ ℕ:
-- Re(∑_{k=1}^{4n+3} k·I^k) = -2(n+1). Combinator rewrites m = 4·(m/4)+3 and
-- uses 97 < m ∧ m%4=3 ⇒ m/4 ≥ 24 to bound -2((m/4)+1) ≤ -50.
import Mathlib
import Problems.Minif2f.amc12a_2009_p15.Defs
import Problems.Minif2f.amc12a_2009_p15.proofs._strategy_s9698

namespace Problems.Minif2f.amc12a_2009_p15

def sum_re_mod3 := @Problems.Minif2f.amc12a_2009_p15.s9698

end Problems.Minif2f.amc12a_2009_p15
