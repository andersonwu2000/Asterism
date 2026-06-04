-- Split the Finset.Icc 1 4 membership into the two bounds 1 ≤ n.factorization 3
-- and n.factorization 3 ≤ 4, then close via Finset.mem_Icc.mpr.
-- Each bound is strictly simpler: a single Nat.le inequality instead of a
-- Finset.Icc membership conjunction.
import Mathlib
import Problems.Minif2f.amc12a_2020_p21.Defs
import Problems.Minif2f.amc12a_2020_p21.proofs._strategy_s9781

namespace Problems.Minif2f.amc12a_2020_p21

def factorization_three_bound := @Problems.Minif2f.amc12a_2020_p21.s9781

end Problems.Minif2f.amc12a_2020_p21
