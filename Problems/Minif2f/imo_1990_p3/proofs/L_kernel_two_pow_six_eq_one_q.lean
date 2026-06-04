-- Decompose `(2:ZMod q)^6 = 1` via orderOf chain: 2^(q-1)=1 (Fermat) + 2^(2m)=1 (m²∣2^m+1)
-- + gcd(q-1,2m) ∣ 6 (only common prime factors are 2,3 since q is minFac of m/3 with 9∤m, m odd).
-- Combinator: orderOf 2 ∣ q-1, orderOf 2 ∣ 2m ⇒ orderOf 2 ∣ gcd ∣ 6 ⇒ 2^6 = 1.
import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs
import Problems.Minif2f.imo_1990_p3.proofs._strategy_s9862

namespace Problems.Minif2f.imo_1990_p3

def kernel_two_pow_six_eq_one_q := @Problems.Minif2f.imo_1990_p3.s9862

end Problems.Minif2f.imo_1990_p3
