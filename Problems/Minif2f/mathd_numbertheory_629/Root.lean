-- IsLeast S 18 splits into membership (18 ∈ S) and lower-bound universal.
-- Membership is a finite arithmetic check (lcm 12 18 = 36, 36^3 = 46656 = 216^2)
-- closed inline by `decide`. The lower-bound universal is delegated as a single
-- Backward sub-goal `lower_bound_18` over `t : ℕ` with the two hypotheses.
import Mathlib
import Problems.Minif2f.mathd_numbertheory_629.Defs
import Problems.Minif2f.mathd_numbertheory_629.proofs._strategy_s9386

namespace Problems.Minif2f.mathd_numbertheory_629

def main := @Problems.Minif2f.mathd_numbertheory_629.s9386

end Problems.Minif2f.mathd_numbertheory_629
