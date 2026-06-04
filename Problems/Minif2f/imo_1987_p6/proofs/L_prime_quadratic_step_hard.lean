-- Reduce primality of `n := i² + i + p` to: every prime divisor of `n`
-- equals `n`. The substantive IMO core argument (a prime divisor `q ≤ √n`
-- would force `k² + k + p = q` for some `k < i` by the strong IH, then a
-- size comparison contradicts `q ≤ √n < n`) is concentrated in the single
-- sub-goal `every_prime_div_eq_self`. The combinator is purely structural:
-- `Nat.minFac n` is a prime divisor, so if every prime divisor equals `n`,
-- then `minFac n = n`, which by `Nat.prime_def_minFac` gives `Nat.Prime n`.
import Mathlib
import Problems.Minif2f.imo_1987_p6.Defs
import Problems.Minif2f.imo_1987_p6.proofs._strategy_s9694

namespace Problems.Minif2f.imo_1987_p6

def prime_quadratic_step_hard := @Problems.Minif2f.imo_1987_p6.s9694

end Problems.Minif2f.imo_1987_p6
