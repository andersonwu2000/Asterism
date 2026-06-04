-- Strategy: weighted AM-GM with uniform weights w_i = 1/n.
-- Sub-goal `amgm_uniform_weights` gives `n * (∏ x)^(1/n) ≤ ∑ x`; rewriting `∏ x = 1`
-- and `1^(1/n) = 1` collapses the LHS to `n`, closing the parent.
import Mathlib
import Problems.Minif2f.algebra_amgm_prod1toneq1_sum1tongeqn.Defs
import Problems.Minif2f.algebra_amgm_prod1toneq1_sum1tongeqn.proofs._strategy_s9616

namespace Problems.Minif2f.algebra_amgm_prod1toneq1_sum1tongeqn

def amgm_real_prod_one_pos := @Problems.Minif2f.algebra_amgm_prod1toneq1_sum1tongeqn.s9616

end Problems.Minif2f.algebra_amgm_prod1toneq1_sum1tongeqn
