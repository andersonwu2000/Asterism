-- Decompose `card_divisors = 3 → factorization = Finsupp.single p 2` into
-- (a) structural extraction `three_div_implies_factor_struct`: the divisor-count
--     hypothesis forces `primeFactors = {p}` together with `factorization p = 2`,
-- (b) Finsupp manipulation `factor_struct_implies_single`: a factorization with
--     support `{p}` and value `2` equals `Finsupp.single p 2` (no count needed).
-- Sub-goal (a) is strictly simpler — it stops at the structural facts, deferring
-- the Finsupp normalization. Sub-goal (b) is pure Finsupp/support algebra and
-- drops the `card_divisors = 3` hypothesis entirely.
import Mathlib
import Problems.Minif2f.mathd_numbertheory_221.Defs
import Problems.Minif2f.mathd_numbertheory_221.proofs._strategy_s9669

namespace Problems.Minif2f.mathd_numbertheory_221

def three_div_implies_fact_eq_single := @Problems.Minif2f.mathd_numbertheory_221.s9669

end Problems.Minif2f.mathd_numbertheory_221
