-- Reduce to closed form: a n = 4 * n + 1 for all n, then evaluate at n = 2010.
-- The closed form sub-goal abstracts the inductive content (solving for p, q from h₁-h₄
-- forces common difference 4; arithmetic recurrence h₀ propagates to all n). Once closed,
-- the parent's specific evaluation at n = 2010 is a pure norm_num check.
import Mathlib
import Problems.Minif2f.amc12a_2010_p10.Defs
import Problems.Minif2f.amc12a_2010_p10.proofs._strategy_s577

namespace Problems.Minif2f.amc12a_2010_p10

def main := @Problems.Minif2f.amc12a_2010_p10.s577

end Problems.Minif2f.amc12a_2010_p10
