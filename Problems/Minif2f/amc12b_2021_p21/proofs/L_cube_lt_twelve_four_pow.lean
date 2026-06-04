-- Sandwich via log monotonicity: positivity of both sides + log-inequality
-- `log 25 + 3 log t < log 12 + t log 4` collapse to the original via
-- `Real.log_lt_log_iff`, `Real.log_mul`, `Real.log_pow`, `Real.log_rpow`.
-- Sub-goal `log_form_cube_four_pow` carries the single analytic core.
import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs
import Problems.Minif2f.amc12b_2021_p21.proofs._strategy_s9840

namespace Problems.Minif2f.amc12b_2021_p21

def cube_lt_twelve_four_pow := @Problems.Minif2f.amc12b_2021_p21.s9840

end Problems.Minif2f.amc12b_2021_p21
