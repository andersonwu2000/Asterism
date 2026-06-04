-- Strip the `Finset.Icc 0 1` membership down to its upper-bound half:
-- the lower bound 0 ≤ n.factorization 7 is `Nat.zero_le`, leaving the
-- single arithmetic claim `n.factorization 7 ≤ 1` derivable from the
-- lcm/gcd identity at prime 7 as one Builder leaf.
import Mathlib
import Problems.Minif2f.amc12a_2020_p21.Defs
import Problems.Minif2f.amc12a_2020_p21.proofs._strategy_s9780

namespace Problems.Minif2f.amc12a_2020_p21

def factorization_seven_bound := @Problems.Minif2f.amc12a_2020_p21.s9780

end Problems.Minif2f.amc12a_2020_p21
