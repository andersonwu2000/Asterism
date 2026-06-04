-- Apply already-proved `eq_three_of_no_large_prime_2` (m=3 from 3∣m, ¬9∣m,
-- and no prime ≥5 dividing m). Sub-goal: derive `∀ p, Prime p → 5 ≤ p → ¬p ∣ m`
-- from `¬ 7 ∣ m` (the gcd/ord-of-2 argument collapses to p=7).
import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs
import Problems.Minif2f.imo_1990_p3.proofs._strategy_s9847

namespace Problems.Minif2f.imo_1990_p3

def m_eq_three_given_hypotheses := @Problems.Minif2f.imo_1990_p3.s9847

end Problems.Minif2f.imo_1990_p3
