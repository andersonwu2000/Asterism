-- Contrapose: if y > 7π/4 then cos y > √2/2, contradicting h2.
-- Sub-goal `cos_gt_on_upper_arc` strictly weaker (drops the upper conjunct
-- and assumes the strict lower bound y > 7π/4 rather than deriving y ≤ 7π/4).
import Mathlib
import Problems.Minif2f.imo_1965_p1.Defs
import Problems.Minif2f.imo_1965_p1.proofs._strategy_s9753

open BigOperators Real Nat Topology Rat

namespace Problems.Minif2f.imo_1965_p1

def upper_arc_bound_2 := @Problems.Minif2f.imo_1965_p1.s9753

end Problems.Minif2f.imo_1965_p1
