-- Decompose `(∏ p ∈ primeFactors, factorization p + 1) = 3 → ∃ p, singleton + multiplicity 2`
-- into (1) `prod_three_primefactors_singleton`: the product-3 forces primeFactors to be a
-- singleton `{p}` with `p` prime, and (2) `factorization_eq_two_of_singleton`: when the
-- support is a singleton and the product is 3, the unique multiplicity must be 2.
-- Each sub-goal is strictly simpler: (1) drops the multiplicity-extraction concern;
-- (2) has the singleton hypothesis as a strengthened input, reducing the product to a
-- single factor `factorization p + 1 = 3`.
import Mathlib
import Problems.Minif2f.mathd_numbertheory_221.Defs
import Problems.Minif2f.mathd_numbertheory_221.proofs._strategy_s9743

namespace Problems.Minif2f.mathd_numbertheory_221

def prod_three_implies_struct := @Problems.Minif2f.mathd_numbertheory_221.s9743

end Problems.Minif2f.mathd_numbertheory_221
