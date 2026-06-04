-- Split the (-50, 50) dichotomy by m % 4. Each residue class has a fixed
-- single-sided bound: m ≡ 0, 1 give Re ≥ 50; m ≡ 2, 3 give Re ≤ -50.
-- Each sub-goal is a single inequality (no disjunction) on a fixed residue,
-- strictly simpler than the parent dichotomy.
import Mathlib
import Problems.Minif2f.amc12a_2009_p15.Defs
import Problems.Minif2f.amc12a_2009_p15.proofs._strategy_s9655

namespace Problems.Minif2f.amc12a_2009_p15

def sum_re_dichotomy := @Problems.Minif2f.amc12a_2009_p15.s9655

end Problems.Minif2f.amc12a_2009_p15
