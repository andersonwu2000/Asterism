-- Direct proof by strong induction: a 0 = 1 > 0 from h₀; for a (m+1), use h₁ m to
-- rewrite as ∏_{k<m+1} a k + 4, then Finset.prod_pos with the strong-induction
-- hypothesis on each factor gives the product > 0, and linarith closes via + 4.
import Mathlib
import Problems.Minif2f.numbertheory_aneqprodakp4_anmsqrtanp1eq2.Defs
import Problems.Minif2f.numbertheory_aneqprodakp4_anmsqrtanp1eq2.proofs._strategy_s9632

namespace Problems.Minif2f.numbertheory_aneqprodakp4_anmsqrtanp1eq2

def seq_pos := @Problems.Minif2f.numbertheory_aneqprodakp4_anmsqrtanp1eq2.s9632

end Problems.Minif2f.numbertheory_aneqprodakp4_anmsqrtanp1eq2
