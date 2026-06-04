-- Two sub-goals + a trivial combinator.
-- A. `n_factorizes_two_three`: τ(2n)=28 ∧ τ(3n)=30 force n = 2^a * 3^b (existence form,
--    structurally bigger — the τ analysis carries the weight).
-- B. `dvd_pow_two_three_coprime_six_eq_one`: pure arithmetic — any divisor of 2^a * 3^b
--    coprime to 6 is 1, by collapsing gcd with the Coprime witness on each prime power.
-- Combinator: feed n's (a,b) factorization into the prime-power lemma at m.
import Mathlib
import Problems.Minif2f.mathd_numbertheory_709.Defs
import Problems.Minif2f.mathd_numbertheory_709.proofs._strategy_s9819

namespace Problems.Minif2f.mathd_numbertheory_709

def coprime_to_6_div_eq_one_2 := @Problems.Minif2f.mathd_numbertheory_709.s9819

end Problems.Minif2f.mathd_numbertheory_709
