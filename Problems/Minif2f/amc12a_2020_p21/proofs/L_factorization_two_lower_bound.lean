-- Reduce `3 ≤ n.factorization 2` to (a) 2^3 ∣ n and (b) n ≠ 0, then close
-- via `Nat.Prime.pow_dvd_iff_le_factorization` on the prime 2. The
-- divisibility carries the 2-adic arithmetic content from the lcm/gcd
-- equation; n ≠ 0 is a side-condition extractable directly from the lcm
-- equation (mirrors the sibling strategy s9795 for prime 5).
import Mathlib
import Problems.Minif2f.amc12a_2020_p21.Defs
import Problems.Minif2f.amc12a_2020_p21.proofs._strategy_s9800

namespace Problems.Minif2f.amc12a_2020_p21

def factorization_two_lower_bound := @Problems.Minif2f.amc12a_2020_p21.s9800

end Problems.Minif2f.amc12a_2020_p21
