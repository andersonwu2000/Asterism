-- Pivot to q := Nat.minFac (m/3) and run the orderOf-gcd argument.
-- Sub-goals: (1) q is prime ≥ 5, (2) gcd(2m, q-1) ∣ 2 (the hard piece — uses
-- minimality of q together with ¬7∣m to collapse odd part of the gcd to 1).
-- Combined with the already-proved 2^(2m) = 1 and Fermat 2^(q-1) = 1 lemmas,
-- orderOf 2 ∣ 2 in ZMod q gives 2^2 = 1.
import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs
import Problems.Minif2f.imo_1990_p3.proofs._strategy_s9854

namespace Problems.Minif2f.imo_1990_p3

def two_sq_eq_one_min_fac_div_three := @Problems.Minif2f.imo_1990_p3.s9854

end Problems.Minif2f.imo_1990_p3
