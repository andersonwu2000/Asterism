-- Sandwich via the cube `t^3`: trivial polynomial step `3*t^2 ≤ t^3` (since t > 3)
-- bridges to the substantive cube-vs-double-exponential dominance `t^3 < RHS`.
-- Combine via `lt_of_le_of_lt` to get the strict bound `3*t^2 < RHS`.
import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs
import Problems.Minif2f.amc12b_2021_p21.proofs._strategy_s9809

namespace Problems.Minif2f.amc12b_2021_p21

def poly_lt_log_dbl_exp := @Problems.Minif2f.amc12b_2021_p21.s9809

end Problems.Minif2f.amc12b_2021_p21
