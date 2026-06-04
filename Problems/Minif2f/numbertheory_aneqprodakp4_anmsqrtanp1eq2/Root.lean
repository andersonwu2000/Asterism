-- Reduce sqrt-equation to two pure arithmetic claims:
--   (1) recursion_squared: a (n+1) = (a n - 2)^2 (from the product recurrence).
--   (2) seq_ge_two       : a n ≥ 2 (so a n - 2 ≥ 0, removing the sqrt branch).
-- Combinator: rewrite a (n+1) by (1), apply Real.sqrt_sq to the nonneg base from (2), ring.
import Mathlib
import Problems.Minif2f.numbertheory_aneqprodakp4_anmsqrtanp1eq2.Defs
import Problems.Minif2f.numbertheory_aneqprodakp4_anmsqrtanp1eq2.proofs._strategy_s9383

namespace Problems.Minif2f.numbertheory_aneqprodakp4_anmsqrtanp1eq2

def main := @Problems.Minif2f.numbertheory_aneqprodakp4_anmsqrtanp1eq2.s9383

end Problems.Minif2f.numbertheory_aneqprodakp4_anmsqrtanp1eq2
