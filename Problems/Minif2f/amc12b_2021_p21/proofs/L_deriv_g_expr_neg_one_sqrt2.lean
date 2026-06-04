-- Direct chain: 2^t * log 2 * log √2 < 2^√2 * t⁻¹ on (1, √2).
-- Bound LHS via 2^t ≤ 2^√2 (monotonicity), then via numeric
-- `log 2 * log √2 < 1/2` (uses `log_sqrt` + `log_two_lt_d9/gt_d9`), then
-- `1/2 < t⁻¹` since `t < √2 < 2` ⇒ `t⁻¹ > 1/2`. Chain closes the
-- subtraction with `linarith`.
import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs
import Problems.Minif2f.amc12b_2021_p21.proofs._strategy_s9829

namespace Problems.Minif2f.amc12b_2021_p21

def deriv_g_expr_neg_one_sqrt2 := @Problems.Minif2f.amc12b_2021_p21.s9829

end Problems.Minif2f.amc12b_2021_p21
