-- Split `3 ≤ n.factorization 5` into (a) 5^3 ∣ n and (b) n ≠ 0, then close
-- via `Nat.Prime.pow_dvd_iff_le_factorization` on the prime 5. The divisibility
-- claim isolates the arithmetic content (lcm/gcd ↔ 5-adic valuation), while
-- n ≠ 0 is a side-condition extracted from the lcm equation.
import Mathlib
import Problems.Minif2f.amc12a_2020_p21.Defs
import Problems.Minif2f.amc12a_2020_p21.proofs._strategy_s9795

namespace Problems.Minif2f.amc12a_2020_p21

def factorization_five_ge_three := @Problems.Minif2f.amc12a_2020_p21.s9795

end Problems.Minif2f.amc12a_2020_p21
