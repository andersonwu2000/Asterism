-- Two-step split isolating 7 as the unique "bad" prime ≥ 5: (A)
-- `seven_not_dvd_n_of_sq` shows 7 ∤ n via 2ⁿ mod 7 cycling {1,2,4} (never -1),
-- using only the n² ∣ 2ⁿ+1 hypothesis (parent's 3∣n + ¬9∣n unused, so strictly
-- simpler scope). (B) `eq_three_given_no_seven` strengthens the parent with
-- the extra hypothesis ¬(7∣n) — the standard proof's minFac(n/3) order-of-2
-- argument gives p ∈ {3,7}, and ¬(7∣n) collapses the case split that killed
-- dead strategy s9590's `no_prime_ge_five_dvd` (which had to handle the
-- gcd(n,p-1)=3 case generically). Combiner trivially chains.
import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs
import Problems.Minif2f.imo_1990_p3.proofs._strategy_s9791

namespace Problems.Minif2f.imo_1990_p3

def eq_three_of_no_nine := @Problems.Minif2f.imo_1990_p3.s9791

end Problems.Minif2f.imo_1990_p3
