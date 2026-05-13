-- Direct telescoping: induction on n with `Finset.sum_Icc_succ_top` peeling off
-- the last term; simp normalizes Nat-subtracted 2^((n+1)-1) = 2^n and the
-- cancellation. Base case n=0 contradicted by h₁; n=1 reduces to a single Icc 1 1.
import Mathlib
import Problems.Minif2f.imo_1966_p4.Defs
import Problems.Minif2f.imo_1966_p4.proofs._strategy_s9640

open BigOperators Real Nat Topology Rat

namespace Problems.Minif2f.imo_1966_p4

def pow_cot_telescope := @Problems.Minif2f.imo_1966_p4.s9640

end Problems.Minif2f.imo_1966_p4
