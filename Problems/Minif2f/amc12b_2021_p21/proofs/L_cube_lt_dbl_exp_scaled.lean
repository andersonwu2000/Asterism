-- Sandwich via 12 * 4^t: 25t³ < 12·4^t (poly-vs-exp, tight at t=3 with margin 93)
-- and 12·4^t ≤ 6·√2^(2^t+2t) (factor 2 absorbed via √2² and 2t+2 ≤ 2^t exponent bound).
import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs
import Problems.Minif2f.amc12b_2021_p21.proofs._strategy_s9837

namespace Problems.Minif2f.amc12b_2021_p21

def cube_lt_dbl_exp_scaled := @Problems.Minif2f.amc12b_2021_p21.s9837

end Problems.Minif2f.amc12b_2021_p21
