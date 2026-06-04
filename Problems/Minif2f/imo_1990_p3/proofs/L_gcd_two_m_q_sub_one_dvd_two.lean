-- Strip the gcd against `2*m` by reducing to a coprimality statement.
-- Sub-goal: `Coprime m (q-1)` where q = Nat.minFac (m/3) — purely a number-theoretic
-- claim, no orderOf or ZMod left. Closer: `d := gcd(2m, q-1) ∣ q-1` together with
-- `Coprime m (q-1)` gives `Coprime m d`, and `Coprime d m + d ∣ 2*m` ⇒ `d ∣ 2`.
import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs
import Problems.Minif2f.imo_1990_p3.proofs._strategy_s9855

namespace Problems.Minif2f.imo_1990_p3

def gcd_two_m_q_sub_one_dvd_two := @Problems.Minif2f.imo_1990_p3.s9855

end Problems.Minif2f.imo_1990_p3
