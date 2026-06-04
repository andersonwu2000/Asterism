-- Forward direction: 3 divisors + x<1000 ⇒ x is in the set.
-- Sub-goal 1 (`three_div_implies_prime_sq`): 3 divisors ⇒ x = p² for some prime p.
-- Sub-goal 2 (`prime_sq_lt_1000_in_set`): p prime ∧ p² < 1000 ⇒ p² ∈ {4,9,…,961}.
-- Combine via `obtain ⟨p, hp, rfl⟩` then apply sub-goal 2.
import Mathlib
import Problems.Minif2f.mathd_numbertheory_221.Defs
import Problems.Minif2f.mathd_numbertheory_221.proofs._strategy_s9416

namespace Problems.Minif2f.mathd_numbertheory_221

def three_div_implies_in_set := @Problems.Minif2f.mathd_numbertheory_221.s9416

end Problems.Minif2f.mathd_numbertheory_221
