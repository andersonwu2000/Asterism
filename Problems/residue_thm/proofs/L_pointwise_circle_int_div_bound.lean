-- ML-style estimate: pointwise kernel bound `‖f w / (w-z)‖ ≤ C/(‖z-z₀‖-R/2)` on the sphere
-- (sub-goal) lifted by `circleIntegral.norm_integral_le_of_norm_le_const` and reassociated by ring.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10444

namespace Problems.residue_thm

def pointwise_circle_int_div_bound := @Problems.residue_thm.s10444

end Problems.residue_thm
