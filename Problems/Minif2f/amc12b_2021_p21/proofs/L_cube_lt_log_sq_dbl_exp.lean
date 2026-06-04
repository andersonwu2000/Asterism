-- Split the strict bound into the analytic cube-vs-scaled-double-exp content
-- (`25 * t^3 < 6 * √2^(2^t + 2t)` for t > 3) and a rational lower bound
-- `6/25 ≤ (log 2)^2 / 2` (numerically tight, provable from `Real.log_two_gt_d9`).
-- Combine multiplicatively: `t^3 < (6/25) * √2^…  ≤  (log 2)^2/2 * √2^…`,
-- using positivity of `√2^…` to scale the rational bound.
import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs
import Problems.Minif2f.amc12b_2021_p21.proofs._strategy_s9832

namespace Problems.Minif2f.amc12b_2021_p21

def cube_lt_log_sq_dbl_exp := @Problems.Minif2f.amc12b_2021_p21.s9832

end Problems.Minif2f.amc12b_2021_p21
