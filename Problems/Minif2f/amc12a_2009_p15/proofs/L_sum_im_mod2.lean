-- Reduce to single closed-form lemma indexed by n ∈ ℕ:
-- Im(∑_{k=1}^{4n+2} k·I^k) = 2n+1. Combinator rewrites m = 4·(m/4)+2 and
-- uses 0 < m ∧ m < 97 ∧ m%4=2 ⇒ m/4 ≤ 23 to bound 2((m/4))+1 ≤ 47 ≤ 48.
import Mathlib
import Problems.Minif2f.amc12a_2009_p15.Defs
import Problems.Minif2f.amc12a_2009_p15.proofs._strategy_s9721

namespace Problems.Minif2f.amc12a_2009_p15

def sum_im_mod2 := @Problems.Minif2f.amc12a_2009_p15.s9721

end Problems.Minif2f.amc12a_2009_p15
