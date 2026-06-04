-- Direct numeric evaluation: instantiate h₀ at x=3/8, y=-2/5, then resolve the floor.
-- Step 1: 3/8 ÷ (-2/5) = -15/16, and -1 ≤ -15/16 < 0, so Int.floor = -1 via Int.floor_eq_iff.
-- Step 2: 3/8 - (-2/5)·(-1) = 3/8 - 2/5 = -1/40 closed by norm_num.
-- No sub-goals: this is leaf arithmetic on concrete rationals.
import Mathlib
import Problems.Minif2f.amc12a_2016_p3.Defs
import Problems.Minif2f.amc12a_2016_p3.proofs._strategy_s585

namespace Problems.Minif2f.amc12a_2016_p3

def main := @Problems.Minif2f.amc12a_2016_p3.s585

end Problems.Minif2f.amc12a_2016_p3
