-- Reduce `3 ∣ n` to identifying the smallest prime factor of n as 3.
-- (a) `min_fac_dvd_three`: order-of-2 argument forces minFac n to divide 3.
-- (b) `min_fac_odd`: n² ∣ (2^n+1) odd ⇒ n odd ⇒ minFac n > 2.
-- A prime > 2 dividing 3 must equal 3; then `Nat.minFac_dvd` finishes.
import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs
import Problems.Minif2f.imo_1990_p3.proofs._strategy_s9433

namespace Problems.Minif2f.imo_1990_p3

def three_dvd_n := @Problems.Minif2f.imo_1990_p3.s9433

end Problems.Minif2f.imo_1990_p3
