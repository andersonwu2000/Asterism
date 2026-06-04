-- Rewrite the RHS to its closed-form value `48 + 49 * I` via `sum_at_97_closed_form`,
-- reducing the goal to "no m ∈ (0, 97) yields the same closed form" — `sum_below_97_neq_target`.
-- Both sub-goals are computationally bounded (single closed value vs. finite case-split)
-- and avoid relating two indexed sums directly.
import Mathlib
import Problems.Minif2f.amc12a_2009_p15.Defs
import Problems.Minif2f.amc12a_2009_p15.proofs._strategy_s9455

namespace Problems.Minif2f.amc12a_2009_p15

def sum_neq_below_97 := @Problems.Minif2f.amc12a_2009_p15.s9455

end Problems.Minif2f.amc12a_2009_p15
