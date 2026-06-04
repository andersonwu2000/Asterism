-- Split membership in Finset.Icc 3 8 into the two one-sided bounds:
-- `3 ≤ n.factorization 2` (lower) and `n.factorization 2 ≤ 8` (upper).
-- Each carries the same hypothesis but proves a single ≤ instead of an Icc.
import Mathlib
import Problems.Minif2f.amc12a_2020_p21.Defs
import Problems.Minif2f.amc12a_2020_p21.proofs._strategy_s9782

namespace Problems.Minif2f.amc12a_2020_p21

def factorization_two_bound := @Problems.Minif2f.amc12a_2020_p21.s9782

end Problems.Minif2f.amc12a_2020_p21
