-- Direct proof: 2008^2 ≡ 4 (mod 10) by norm_num; 2^2008 ≡ 6 (mod 10) via
-- 4-cycle induction (2008 = 4*501 + 4); then Nat.add_mod closes the goal.
import Mathlib
import Problems.Minif2f.amc12a_2008_p15.Defs
import Problems.Minif2f.amc12a_2008_p15.proofs._strategy_s9369

namespace Problems.Minif2f.amc12a_2008_p15

def k_mod_ten := @Problems.Minif2f.amc12a_2008_p15.s9369

end Problems.Minif2f.amc12a_2008_p15
