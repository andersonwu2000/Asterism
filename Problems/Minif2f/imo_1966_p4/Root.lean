-- Decomposition: pointwise identity 1/sin(2^k·x) = cot(2^(k-1)·x) - cot(2^k·x)
-- combined with telescoping sum of cot differences. Combinator: Finset.sum_congr to
-- rewrite each summand via pointwise identity, then exact application of telescope.
import Mathlib
import Problems.Minif2f.imo_1966_p4.Defs
import Problems.Minif2f.imo_1966_p4.proofs._strategy_s9481

open BigOperators Real Nat Topology Rat

namespace Problems.Minif2f.imo_1966_p4

def main := @Problems.Minif2f.imo_1966_p4.s9481

end Problems.Minif2f.imo_1966_p4
