-- Decompose `a n ≥ 2` (for n ≥ 1) into the universal claim `0 < a n`.
-- Combinator: write n = m+1, apply h₁ so a (m+1) = (∏ k ∈ range (m+1), a k) + 4;
-- positivity of every factor gives the product > 0 via `Finset.prod_pos`, then linarith
-- closes prod + 4 ≥ 2.
import Mathlib
import Problems.Minif2f.numbertheory_aneqprodakp4_anmsqrtanp1eq2.Defs
import Problems.Minif2f.numbertheory_aneqprodakp4_anmsqrtanp1eq2.proofs._strategy_s9467

namespace Problems.Minif2f.numbertheory_aneqprodakp4_anmsqrtanp1eq2

def seq_ge_two := @Problems.Minif2f.numbertheory_aneqprodakp4_anmsqrtanp1eq2.s9467

end Problems.Minif2f.numbertheory_aneqprodakp4_anmsqrtanp1eq2
