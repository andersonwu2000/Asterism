-- Factor RHS into `(log 2)^2 / 2 * sqrt(2)^(2^t + 2t)` via the identities
-- `log(sqrt 2) = (log 2)/2` and `(2:ℝ)^t = sqrt(2)^(2t)`, then compare cube to
-- the rewritten lower bound. Sub-goal 1 is a pure rpow/log identity (universal
-- in t); sub-goal 2 carries the analytic cube-vs-double-exp content on `t > 3`.
import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs
import Problems.Minif2f.amc12b_2021_p21.proofs._strategy_s9824

namespace Problems.Minif2f.amc12b_2021_p21

def cube_lt_rhs := @Problems.Minif2f.amc12b_2021_p21.s9824

end Problems.Minif2f.amc12b_2021_p21
