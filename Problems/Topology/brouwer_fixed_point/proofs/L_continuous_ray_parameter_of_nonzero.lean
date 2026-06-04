-- Pick the explicit non-negative root of the quadratic ‖x + t · v x‖² = 1:
-- t x := (√(⟨x,vx⟩² + ‖vx‖²·(1-‖x‖²)) - ⟨x,vx⟩) / ‖vx‖².
-- Three sub-goals verify (i) continuity of this formula on closedBall (uses
-- hvcont, hvne), (ii) the formula satisfies ‖x + t·v x‖ = 1 (algebraic, uses
-- hvne to handle division), (iii) on the unit sphere the formula collapses
-- to 0 because 1-‖x‖²=0 and ⟨x,vx⟩ ≥ 0 (hvinner) makes √(⟨x,vx⟩²)=⟨x,vx⟩.
import Mathlib
import Problems.Topology.brouwer_fixed_point.Defs
import Problems.Topology.brouwer_fixed_point.proofs._strategy_s10821

namespace Problems.Topology.brouwer_fixed_point

def continuous_ray_parameter_of_nonzero := @Problems.Topology.brouwer_fixed_point.s10821

end Problems.Topology.brouwer_fixed_point
