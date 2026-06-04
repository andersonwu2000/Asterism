-- Split: (A) every divisor of n coprime to 6 equals 1 (τ(2n)=28 ∧ τ(3n)=30 ⇒
--   coprime-to-6 divisors have τ=1); (B) structural step — a prime p ≠ 2, 3 is
--   coprime to 6, so (A) forces p = 1, contradicting primality.
-- Combinator: feed (A)'s smoothness witness into (B) at this specific n.
import Mathlib
import Problems.Minif2f.mathd_numbertheory_709.Defs
import Problems.Minif2f.mathd_numbertheory_709.proofs._strategy_s9834

namespace Problems.Minif2f.mathd_numbertheory_709

def n_smooth_at_two_three_2 := @Problems.Minif2f.mathd_numbertheory_709.s9834

end Problems.Minif2f.mathd_numbertheory_709
