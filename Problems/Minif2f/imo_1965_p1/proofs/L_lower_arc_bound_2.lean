-- Contrapositive: if y < π/4 (with 0 ≤ y), then cos y > √2/2, contradicting cos y ≤ √2/2.
-- Single sub-goal `cos_gt_sqrt2_half_below_pi_div_four` captures the strict cos lower bound
-- on [0, π/4); upper bound y ≤ 2π is unused on this branch.
import Mathlib
import Problems.Minif2f.imo_1965_p1.Defs
import Problems.Minif2f.imo_1965_p1.proofs._strategy_s9752

open BigOperators Real Nat Topology Rat

namespace Problems.Minif2f.imo_1965_p1

def lower_arc_bound_2 := @Problems.Minif2f.imo_1965_p1.s9752

end Problems.Minif2f.imo_1965_p1
