-- Squeeze a between two bounds derived from prime triplet constraints.
-- (1) a ≥ 5 rules out a=2,3 (a-2 ∈ {0,1} not prime).
-- (2) a ≤ 5 rules out a ≥ 7 via mod 3 argument (one of a±2 divisible by 3).
import Mathlib
import Problems.Minif2f.amc12b_2002_p11.Defs
import Problems.Minif2f.amc12b_2002_p11.proofs._strategy_s9448

namespace Problems.Minif2f.amc12b_2002_p11

def a_eq_five_when_b_two := @Problems.Minif2f.amc12b_2002_p11.s9448

end Problems.Minif2f.amc12b_2002_p11
