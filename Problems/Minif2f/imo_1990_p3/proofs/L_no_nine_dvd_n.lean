-- Two-step split aligned with parent strategy (LTE bound on v_3):
-- (1) `n_is_odd`: n²∣(2^n+1) forces n odd (since 2^n+1 is odd).
-- (2) `nine_not_dvd_of_odd`: with Odd n in hand, the LTE identity
--     v_3(2^n+1) = 1 + v_3(n) combined with n²∣(2^n+1) gives v_3(n) ≤ 1,
--     ruling out 9 ∣ n.
import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs
import Problems.Minif2f.imo_1990_p3.proofs._strategy_s9490

namespace Problems.Minif2f.imo_1990_p3

def no_nine_dvd_n := @Problems.Minif2f.imo_1990_p3.s9490

end Problems.Minif2f.imo_1990_p3
