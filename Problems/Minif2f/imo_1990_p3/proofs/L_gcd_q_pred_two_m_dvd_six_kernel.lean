-- Reduce gcd(q-1, 2m) ∣ 6 to coprimality `(m/3).Coprime (q-1)` where q = Nat.minFac (m/3).
-- Since 2m = 6 * (m/3) and gcd(q-1, m/3) = 1 (smallest-prime-factor argument),
-- `gcd(q-1, 6*(m/3)) = gcd(q-1, 6) ∣ 6`.
import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs
import Problems.Minif2f.imo_1990_p3.proofs._strategy_s9865

namespace Problems.Minif2f.imo_1990_p3

def gcd_q_pred_two_m_dvd_six_kernel := @Problems.Minif2f.imo_1990_p3.s9865

end Problems.Minif2f.imo_1990_p3
