-- Direct proof (sorry-free leaf): show Nat.minFac (m/3) is prime and ≥ 5.
-- m odd (else 2∣m forces 2∣2^m+1 contradiction), 3∣m so m = 3·(m/3); p∣m with p≥5
-- forces p∣(m/3) hence m/3 ≥ 2 ⇒ minFac is prime. Exclude 2 (m odd), 3 (would
-- give 9∣m), 4 (not prime); two_le + omega ⇒ minFac ≥ 5.
import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs
import Problems.Minif2f.imo_1990_p3.proofs._strategy_s9866

namespace Problems.Minif2f.imo_1990_p3

def min_fac_div_three_prime_ge_five_2 := @Problems.Minif2f.imo_1990_p3.s9866

end Problems.Minif2f.imo_1990_p3
