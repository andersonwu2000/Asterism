-- (1) prove n is 2,3-smooth (only primes dividing n are 2 or 3): the full τ-analysis
--     on τ(2n)=28 and τ(3n)=30 forces the coprime-to-6 part of n to have one divisor;
-- (2) lift smoothness to existence of (a, b) with n = 2^a * 3^b via the standard
--     factorization (this matches the already-proved `exists_two_three_factorization`).
-- Combinator: apply (2) to the smoothness fact produced by (1).
import Mathlib
import Problems.Minif2f.mathd_numbertheory_709.Defs
import Problems.Minif2f.mathd_numbertheory_709.proofs._strategy_s9785

namespace Problems.Minif2f.mathd_numbertheory_709

def pow_two_three_factorization := @Problems.Minif2f.mathd_numbertheory_709.s9785

end Problems.Minif2f.mathd_numbertheory_709
