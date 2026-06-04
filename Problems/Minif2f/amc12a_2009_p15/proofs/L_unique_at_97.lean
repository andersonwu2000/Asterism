-- Trichotomy on `m` vs `97`: m < 97 / m = 97 / m > 97. The equal branch closes
-- directly; the two non-equal branches contradict h₁ via dedicated sub-lemmas
-- `sum_neq_below_97` (finite case-split, 0 < m < 97) and `sum_neq_above_97`
-- (uses closed-form / magnitude growth of the partial sum for m > 97).
import Mathlib
import Problems.Minif2f.amc12a_2009_p15.Defs
import Problems.Minif2f.amc12a_2009_p15.proofs._strategy_s9349

namespace Problems.Minif2f.amc12a_2009_p15

def unique_at_97 := @Problems.Minif2f.amc12a_2009_p15.s9349

end Problems.Minif2f.amc12a_2009_p15
