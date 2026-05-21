-- Pointwise kernel-decay + ML inequality. On the sphere of radius r, reverse
-- triangle gives `|w - z| ≥ dist z z₀ - r > 0`, so `‖f w / (w - z)‖ ≤ M / (dist z z₀ - r)`;
-- `circleIntegral.norm_integral_le_of_norm_le_const` lifts to a `2π·r` factor, and
-- `mul_div_assoc` reassociates to the stated bound.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10440

namespace Problems.residue_thm

def circle_integral_div_sub_norm_bound := @Problems.residue_thm.s10440

end Problems.residue_thm
