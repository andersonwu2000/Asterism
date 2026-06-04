-- Split into: (A) every divisor of n coprime to 6 must equal 1
--   (the τ(2n)=28 ∧ τ(3n)=30 ⇒ coprime-to-6 part is τ=1 work);
-- (B) the structural step: a prime p ≠ 2, 3 is coprime to 6, so under (A) it
--   cannot divide n.
-- Combinator: feed (A) into (B) at this specific n.
import Mathlib
import Problems.Minif2f.mathd_numbertheory_709.Defs
import Problems.Minif2f.mathd_numbertheory_709.proofs._strategy_s9806

namespace Problems.Minif2f.mathd_numbertheory_709

def n_smooth_at_two_three := @Problems.Minif2f.mathd_numbertheory_709.s9806

end Problems.Minif2f.mathd_numbertheory_709
