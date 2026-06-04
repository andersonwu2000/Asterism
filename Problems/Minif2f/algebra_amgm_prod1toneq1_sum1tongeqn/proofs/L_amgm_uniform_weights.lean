-- AM-GM with uniform weights. Sub-goal `geom_le_arith_mean_avg` provides the
-- average form `(∏ x)^(1/n) ≤ (1/n) * ∑ x`; we multiply both sides by `n > 0`,
-- the `n * (1/n)` cancels, yielding `n * (∏ x)^(1/n) ≤ ∑ x`. The `∏ x = 1`
-- hypothesis is unused at this level; it lives at the parent.
import Mathlib
import Problems.Minif2f.algebra_amgm_prod1toneq1_sum1tongeqn.Defs
import Problems.Minif2f.algebra_amgm_prod1toneq1_sum1tongeqn.proofs._strategy_s9658

namespace Problems.Minif2f.algebra_amgm_prod1toneq1_sum1tongeqn

def amgm_uniform_weights := @Problems.Minif2f.algebra_amgm_prod1toneq1_sum1tongeqn.s9658

end Problems.Minif2f.algebra_amgm_prod1toneq1_sum1tongeqn
