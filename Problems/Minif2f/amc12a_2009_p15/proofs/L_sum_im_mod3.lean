-- Reduce to one closed-form lemma indexed by n ∈ ℕ:
-- Im(∑_{k=1}^{4n+3} k·I^k) = -2n - 2. Combinator rewrites m = 4·(m/4)+3 and
-- uses 0 ≤ m/4 (cast to ℝ) to bound -2(m/4) - 2 ≤ -2 ≤ 48.
import Mathlib
import Problems.Minif2f.amc12a_2009_p15.Defs
import Problems.Minif2f.amc12a_2009_p15.proofs._strategy_s9722

namespace Problems.Minif2f.amc12a_2009_p15

def sum_im_mod3 := @Problems.Minif2f.amc12a_2009_p15.s9722

end Problems.Minif2f.amc12a_2009_p15
