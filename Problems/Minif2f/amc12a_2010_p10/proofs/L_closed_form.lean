-- Decompose closed-form proof in two steps:
--   sub_1 `p_eq_five`: derive p = 5 from the linear system h₀ at n=1,2 with h₁..h₄
--     (no induction; pure linear arithmetic on a 1..a 4).
--   sub_2 `closed_form_with_p`: with p = 5 in hand (so a 1 = 5, a 2 = 9), induct on
--     the second-order recurrence h₀ to obtain a n = 4 n + 1 for all n.
-- The combinator chains sub_1 into sub_2; q is never needed past sub_2's hypotheses.
import Mathlib
import Problems.Minif2f.amc12a_2010_p10.Defs
import Problems.Minif2f.amc12a_2010_p10.proofs._strategy_s9259

namespace Problems.Minif2f.amc12a_2010_p10

def closed_form := @Problems.Minif2f.amc12a_2010_p10.s9259

end Problems.Minif2f.amc12a_2010_p10
