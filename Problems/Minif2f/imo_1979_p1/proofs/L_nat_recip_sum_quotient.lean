-- Decomposition: invoke an abstract lemma `sum_recip_eq_quotient_of_pos_nat` that for any
-- finite set of positive nat-valued denominators expresses ∑ 1/f j as n / ∏ f j (cast to ℝ).
-- Specialize at f j := (660+j)*(1319-j) on Finset.range 330 (positivity from omega bounds).
import Mathlib
import Problems.Minif2f.imo_1979_p1.Defs
import Problems.Minif2f.imo_1979_p1.proofs._strategy_s9670

namespace Problems.Minif2f.imo_1979_p1

def nat_recip_sum_quotient := @Problems.Minif2f.imo_1979_p1.s9670

end Problems.Minif2f.imo_1979_p1
