-- Reduce to one closed-form lemma indexed by n ∈ ℕ:
-- Re(∑_{k=1}^{4n+2} k·I^k) = -2n − 2. Apply at n = 24+j (so 98+4j = 4·(24+j)+2)
-- and `push_cast; ring` closes against −50 − 2j.
import Mathlib
import Problems.Minif2f.amc12a_2009_p15.Defs
import Problems.Minif2f.amc12a_2009_p15.proofs._strategy_s9733

namespace Problems.Minif2f.amc12a_2009_p15

def sum_re_98_plus_4j_eq := @Problems.Minif2f.amc12a_2009_p15.s9733

end Problems.Minif2f.amc12a_2009_p15
