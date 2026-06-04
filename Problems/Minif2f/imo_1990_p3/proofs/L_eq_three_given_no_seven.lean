-- Reduce to: no prime ≥ 5 divides m. With ¬(7∣m) added to parent's hypotheses,
-- the gcd(n, p-1) order-of-2 case split that killed dead s9590 collapses (only
-- p=7 was the bad case). Then chain with the already-proved
-- `eq_three_of_no_large_prime`.
import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs
import Problems.Minif2f.imo_1990_p3.proofs._strategy_s9810

namespace Problems.Minif2f.imo_1990_p3

def eq_three_given_no_seven := @Problems.Minif2f.imo_1990_p3.s9810

end Problems.Minif2f.imo_1990_p3
