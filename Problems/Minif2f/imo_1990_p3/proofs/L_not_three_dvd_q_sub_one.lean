-- Decompose ¬ 3 ∣ (minFac(m/3) - 1) by contradiction; assume 3 ∣ q-1.
-- (A) `kernel_two_pow_six_eq_one_q`: 3∣q-1 + 9∤m + odd m + Fermat ⇒ orderOf(2 mod q) ∣ 6.
-- (B) `not_two_pow_six_eq_one_q`: 2^6=1 in ZMod q ⇒ q∣63 ⇒ q=7 (q prime ≥5), but ¬7∣m.
import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs
import Problems.Minif2f.imo_1990_p3.proofs._strategy_s9861

namespace Problems.Minif2f.imo_1990_p3

def not_three_dvd_q_sub_one := @Problems.Minif2f.imo_1990_p3.s9861

end Problems.Minif2f.imo_1990_p3
