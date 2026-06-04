-- Decompose τ(2n)=28 ∧ τ(3n)=30 ∧ n=2^a·3^b into:
--   A. τ(2·2^a·3^b) = (a+2)(b+1)   — combinatorial fact, no parent hypotheses
--   B. τ(3·2^a·3^b) = (a+1)(b+2)   — combinatorial fact, no parent hypotheses
--   C. (a+2)(b+1)=28 → (a+1)(b+2)=30 → 2^a·3^b = 864   — pure ℕ-arithmetic system
-- Combinator: subst hn, rewrite h₁ and h₂ by A/B, apply C.
import Mathlib
import Problems.Minif2f.mathd_numbertheory_709.Defs
import Problems.Minif2f.mathd_numbertheory_709.proofs._strategy_s9740

namespace Problems.Minif2f.mathd_numbertheory_709

def factorization_forces_864 := @Problems.Minif2f.mathd_numbertheory_709.s9740

end Problems.Minif2f.mathd_numbertheory_709
