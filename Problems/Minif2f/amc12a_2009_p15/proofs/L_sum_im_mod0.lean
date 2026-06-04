-- Reduce to closed-form: for any n, Im(∑_{k=1}^{4n} k·iᵏ) = -2n.
-- Then m % 4 = 0 ⇒ m = 4·(m/4), giving Im = -2·(m/4) ≤ 0 ≤ 48 trivially.
import Mathlib
import Problems.Minif2f.amc12a_2009_p15.Defs
import Problems.Minif2f.amc12a_2009_p15.proofs._strategy_s9719

namespace Problems.Minif2f.amc12a_2009_p15

def sum_im_mod0 := @Problems.Minif2f.amc12a_2009_p15.s9719

end Problems.Minif2f.amc12a_2009_p15
