-- Split into: (A) the 2-3-smooth factorization `∃ a b, n = 2^a * 3^b`
--   (full τ-analysis lives here — Backward sub-goal);
-- (B) pure ℕ-arithmetic bound on `((Nat.divisors (2^a * 3^b)).filter (Coprime · 6)).card`
--   (independent of n's hypotheses — Builder sub-goal).
-- Combinator: obtain (a, b) from (A); rewrite `n` and apply (B).
import Mathlib
import Problems.Minif2f.mathd_numbertheory_709.Defs
import Problems.Minif2f.mathd_numbertheory_709.proofs._strategy_s9768

namespace Problems.Minif2f.mathd_numbertheory_709

def coprime_to_6_div_card_le_one := @Problems.Minif2f.mathd_numbertheory_709.s9768

end Problems.Minif2f.mathd_numbertheory_709
