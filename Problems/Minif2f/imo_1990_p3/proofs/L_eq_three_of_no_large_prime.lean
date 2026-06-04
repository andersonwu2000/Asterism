-- Abstract away the `n² ∣ 2ⁿ+1` hypothesis: it is only used to force `Odd n`.
-- (a) `odd_of_sq_dvd_pow_succ`: parity argument — already proved as `n_is_odd`.
-- (b) `eq_three_of_odd_no_large_prime`: with `Odd m` in place of the divisibility
--     hypothesis, the conclusion follows from `minFac`-style structure +
--     `3 ∣ m`, `¬ 9 ∣ m`, no prime ≥ 5 dividing `m`. Cleaner sub-goal shape.
import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs
import Problems.Minif2f.imo_1990_p3.proofs._strategy_s9651

namespace Problems.Minif2f.imo_1990_p3

def eq_three_of_no_large_prime := @Problems.Minif2f.imo_1990_p3.s9651

end Problems.Minif2f.imo_1990_p3
