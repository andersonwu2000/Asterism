-- Split `n.factorization 5 = 3` into the two inequalities and close by le_antisymm.
-- Each direction is strictly simpler: a single Nat.le inequality on the same
-- hypothesis, rather than equality. The two bounds are independent — the upper
-- bound rules out k ≥ 4, the lower bound rules out k ∈ {0,1,2}.
import Mathlib
import Problems.Minif2f.amc12a_2020_p21.Defs
import Problems.Minif2f.amc12a_2020_p21.proofs._strategy_s9778

namespace Problems.Minif2f.amc12a_2020_p21

def factorization_five_eq_three := @Problems.Minif2f.amc12a_2020_p21.s9778

end Problems.Minif2f.amc12a_2020_p21
