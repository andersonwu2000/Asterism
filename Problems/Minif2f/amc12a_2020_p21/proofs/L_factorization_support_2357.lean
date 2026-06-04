-- Decomposition: split into (1) extracting `n ∣ 5 * 10!` from the
-- lcm/gcd hypothesis (chain `n ∣ lcm 5! n = 5·gcd 10! n ∣ 5·10!`), and
-- (2) deducing the canonical 2/3/5/7 product form from `n ∣ 5·10!`
-- (since `5·10! = 2^8·3^4·5^3·7`, its divisors have factorization
-- support ⊆ {2,3,5,7}).  Combinator chains the two via the new premise.
import Mathlib
import Problems.Minif2f.amc12a_2020_p21.Defs
import Problems.Minif2f.amc12a_2020_p21.proofs._strategy_s9779

namespace Problems.Minif2f.amc12a_2020_p21

def factorization_support_2357 := @Problems.Minif2f.amc12a_2020_p21.s9779

end Problems.Minif2f.amc12a_2020_p21
