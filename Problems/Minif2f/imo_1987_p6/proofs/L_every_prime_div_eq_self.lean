-- Reduce "every prime divisor of n = i²+i+p equals n" to "no prime divisor q
-- satisfies q² ≤ n". The substantive IMO core argument (find k ≤ (q-1)/2
-- with q | f(k), use IH to get q = k²+k+p, then derive p² ≤ p²-2p+2) is
-- concentrated in `no_small_prime_factor`. The combinator is purely
-- structural: minFac n is a prime divisor, sub-goal forces (minFac n)² > n,
-- so by Nat.minFac_le_div contrapositive n is prime, hence q = n.
import Mathlib
import Problems.Minif2f.imo_1987_p6.Defs
import Problems.Minif2f.imo_1987_p6.proofs._strategy_s9735

namespace Problems.Minif2f.imo_1987_p6

def every_prime_div_eq_self := @Problems.Minif2f.imo_1987_p6.s9735

end Problems.Minif2f.imo_1987_p6
