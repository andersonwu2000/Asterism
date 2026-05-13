-- Direct telescoping sum proof — pure algebraic identity (h₀ and h₁ unused).
-- Induction on n: base n=0 closes by `simp` (empty sum on the left, 0 on right since 2^0*x=x).
-- Step uses `Finset.sum_Icc_succ_top` to peel the last term off Icc 1 (m+1), then either
-- handles m=0 directly or applies the IH and closes with `simp` (telescoping cancellation).
import Mathlib
import Problems.Minif2f.imo_1966_p4.Defs
import Problems.Minif2f.imo_1966_p4.proofs._strategy_s9422

open BigOperators Real Nat Topology Rat

namespace Problems.Minif2f.imo_1966_p4

def pow_cot_sum_telescopes := @Problems.Minif2f.imo_1966_p4.s9422

end Problems.Minif2f.imo_1966_p4
