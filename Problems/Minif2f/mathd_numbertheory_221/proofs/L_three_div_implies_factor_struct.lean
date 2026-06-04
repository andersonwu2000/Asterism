-- Decompose `divisors.card = 3 → ∃ p prime, primeFactors = {p} ∧ factorization p = 2`
-- into (a) rewriting via `Nat.card_divisors` to the prime-factorization product form
-- (b) the combinatorial sub-goal `prod_three_implies_struct`: a product of `(k_i + 1)`
-- over primeFactors equaling 3 forces a singleton support with multiplicity 2.
-- The sub-goal drops `divisors.card`, replaces it with the algebraic product hypothesis,
-- and becomes a pure factorization-support argument independent of the divisor count.
import Mathlib
import Problems.Minif2f.mathd_numbertheory_221.Defs
import Problems.Minif2f.mathd_numbertheory_221.proofs._strategy_s9705

namespace Problems.Minif2f.mathd_numbertheory_221

def three_div_implies_factor_struct := @Problems.Minif2f.mathd_numbertheory_221.s9705

end Problems.Minif2f.mathd_numbertheory_221
