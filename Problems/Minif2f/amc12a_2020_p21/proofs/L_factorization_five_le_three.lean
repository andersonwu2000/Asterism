-- Pivot through divisibility: combine two strictly simpler lemmas.
-- (1) `n_dvd_five_mul_ten_factorial` — already proved sibling — turns
--     the lcm/gcd hypothesis into `n ∣ 5 * 10!`.
-- (2) `dvd_five_mul_ten_factorial_factorization_five_le_three` —
--     pure number-theoretic step, no parent hypothesis: any divisor of
--     `5 * 10! = 2^8·3^4·5^3·7` has its 5-adic valuation ≤ 3.
import Mathlib
import Problems.Minif2f.amc12a_2020_p21.Defs
import Problems.Minif2f.amc12a_2020_p21.proofs._strategy_s9796

namespace Problems.Minif2f.amc12a_2020_p21

def factorization_five_le_three := @Problems.Minif2f.amc12a_2020_p21.s9796

end Problems.Minif2f.amc12a_2020_p21
