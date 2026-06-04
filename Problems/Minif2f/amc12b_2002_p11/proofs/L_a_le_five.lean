-- Case split on a % 3: in any prime triplet {a-2, a, a+2}, exactly one of
-- the three values is ≡ 0 (mod 3). Each residue class delegates to a sub-goal
-- that uses the corresponding prime hypothesis to bound a ≤ 5.
import Mathlib
import Problems.Minif2f.amc12b_2002_p11.Defs
import Problems.Minif2f.amc12b_2002_p11.proofs._strategy_s9624

namespace Problems.Minif2f.amc12b_2002_p11

def a_le_five := @Problems.Minif2f.amc12b_2002_p11.s9624

end Problems.Minif2f.amc12b_2002_p11
