-- Reduce to one closed-form lemma indexed by n ∈ ℕ:
-- Re(∑_{k=1}^{4n+1} k·I^k) = 2n. Combinator rewrites m = 4·(m/4)+1 and
-- closes by `push_cast; ring` against the parent RHS ((m-1)/2).
import Mathlib
import Problems.Minif2f.amc12a_2009_p15.Defs
import Problems.Minif2f.amc12a_2009_p15.proofs._strategy_s9732

namespace Problems.Minif2f.amc12a_2009_p15

def closed_form_re_mod1 := @Problems.Minif2f.amc12a_2009_p15.s9732

end Problems.Minif2f.amc12a_2009_p15
