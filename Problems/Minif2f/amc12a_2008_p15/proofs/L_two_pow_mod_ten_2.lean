-- Direct proof reusing the periodic lemma 2^(4k+4) ≡ 6 (mod 10).
-- Inline an induction on k (base 2^4 = 16, step pow_add + Nat.mul_mod),
-- then express m as 4*(m/4 - 1) + 4 via omega and apply.
import Mathlib
import Problems.Minif2f.amc12a_2008_p15.Defs
import Problems.Minif2f.amc12a_2008_p15.proofs._strategy_s9464

namespace Problems.Minif2f.amc12a_2008_p15

def two_pow_mod_ten_2 := @Problems.Minif2f.amc12a_2008_p15.s9464

end Problems.Minif2f.amc12a_2008_p15
