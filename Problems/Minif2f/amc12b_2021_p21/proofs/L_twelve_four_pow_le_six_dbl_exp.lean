-- Sandwich via `6 * sqrt 2 ^ (4*t + 2)`: rewrite LHS using `sqrt 2 ^ 2 = 2`
-- and `(sqrt 2)^4 = 4`, then use monotonicity of `sqrt 2 ^ ·` (since `1 ≤ sqrt 2`)
-- with the exponent bound `4*t + 2 ≤ 2^t + 2*t` (the actual content; tight at t=3).
import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs
import Problems.Minif2f.amc12b_2021_p21.proofs._strategy_s9841

namespace Problems.Minif2f.amc12b_2021_p21

def twelve_four_pow_le_six_dbl_exp := @Problems.Minif2f.amc12b_2021_p21.s9841

end Problems.Minif2f.amc12b_2021_p21
