-- Reduce to the closed-form: for any n, Re ∑_{k=1}^{4n} k·iᵏ = 2n.
-- Then m > 97 ∧ m ≡ 0 (mod 4) ⇒ m = 4·(m/4) with m/4 ≥ 25, giving Re ≥ 50.
import Mathlib
import Problems.Minif2f.amc12a_2009_p15.Defs
import Problems.Minif2f.amc12a_2009_p15.proofs._strategy_s9695

namespace Problems.Minif2f.amc12a_2009_p15

def sum_re_mod0 := @Problems.Minif2f.amc12a_2009_p15.s9695

end Problems.Minif2f.amc12a_2009_p15
