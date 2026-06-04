-- (1) `n_smooth_at_two_three`: only primes dividing n are 2 or 3 (the τ-analysis carries
--     all the weight here — structurally bigger, Backward-style).
-- (2) `factorize_when_two_three_smooth`: lift smoothness to existence of (a, b)
--     by choosing a := v₂(n), b := v₃(n) via the factorization equation.
-- Combinator: apply (2) to the smoothness witness produced by (1).
import Mathlib
import Problems.Minif2f.mathd_numbertheory_709.Defs
import Problems.Minif2f.mathd_numbertheory_709.proofs._strategy_s9828

namespace Problems.Minif2f.mathd_numbertheory_709

def n_factorizes_two_three := @Problems.Minif2f.mathd_numbertheory_709.s9828

end Problems.Minif2f.mathd_numbertheory_709
