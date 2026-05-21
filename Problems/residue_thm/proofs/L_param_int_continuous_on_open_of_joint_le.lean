-- Localize the open-set continuity goal to pointwise ContinuousAt at every
-- `w₀ ∈ U`, then shrink to a closed ball `closedBall w₀ (r/2) ⊆ U` (compact)
-- and hand off to the closed-ball DCT core. The single sub-goal
-- `param_int_cont_at_closed_ball_le` carries `a ≤ b`, so the parametric DCT
-- (`continuousAt_of_dominated_interval` with a constant bound from compactness)
-- applies cleanly — this is what was missing in the earlier `_of_joint`
-- (no `a ≤ b`) chain that died at the closed-ball leaf.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10656

namespace Problems.residue_thm

def param_int_continuous_on_open_of_joint_le := @Problems.residue_thm.s10656

end Problems.residue_thm
