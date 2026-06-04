-- Reduce f(2017) to the closed form for odd inputs: f(2k+1) = 2k+2.
-- Sub-goal `odd_value` proves the general odd-index formula by induction on k;
-- specializing at k = 1008 and simplifying with norm_num closes f 2017 = 2018.
import Mathlib
import Problems.Minif2f.amc12a_2017_p7.Defs
import Problems.Minif2f.amc12a_2017_p7.proofs._strategy_s587

namespace Problems.Minif2f.amc12a_2017_p7

def main := @Problems.Minif2f.amc12a_2017_p7.s587

end Problems.Minif2f.amc12a_2017_p7
