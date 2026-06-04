-- Split into two independent claims pinning x and y individually, combined by `omega`.
-- Sub-goal `x_eq_four`: x = 4 from 2^x * 3^y = 1296 (unique factorization on prime 2).
-- Sub-goal `y_eq_four`: y = 4 from 2^x * 3^y = 1296 (unique factorization on prime 3).
-- Each sub-goal is strictly simpler (one variable pinned, not a sum), and together pin x+y=8.
import Mathlib
import Problems.Minif2f.amc12b_2004_p3.Defs
import Problems.Minif2f.amc12b_2004_p3.proofs._strategy_s9254

namespace Problems.Minif2f.amc12b_2004_p3

def main := @Problems.Minif2f.amc12b_2004_p3.s9254

end Problems.Minif2f.amc12b_2004_p3
