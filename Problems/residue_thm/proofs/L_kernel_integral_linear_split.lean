-- Split kernel as `f w / (w - z) = f z * (w - z)⁻¹ + (f w - f z) / (w - z)` on each
-- circle via the abstract sub-goal `circle_kernel_linear_split`, applied with the
-- per-radius continuity-and-off-circle hypotheses; the parent identity then closes
-- by subtracting the two splits (`ring`). Sub-goal is strictly simpler: it isolates
-- the circle-integral linearity + pointwise algebra at a single radius, drops the
-- two-radius coupling, and weakens the `AnalyticOn` hypothesis to plain
-- `ContinuousOn` on one sphere — enough to invoke
-- `circleIntegral.integral_congr` + `circleIntegral.integral_add` +
-- `circleIntegral.integral_const_mul`.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10439

namespace Problems.residue_thm

def kernel_integral_linear_split := @Problems.residue_thm.s10439

end Problems.residue_thm
