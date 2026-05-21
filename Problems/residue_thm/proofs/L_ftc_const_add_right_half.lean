-- Direct FTC. For `t ∈ Ioo (1/2) 1`, `Icc (1/2) 1 ∈ 𝓝 t` upgrades the
-- `ContinuousOn` hypothesis to `ContinuousAt g t`, `IntervalIntegrable g (1/2) t`,
-- and `StronglyMeasurableAtFilter g (𝓝 t)` (via `isOpen_Ioo`); then apply
-- `intervalIntegral.integral_hasDerivAt_right` + `HasDerivAt.const_add C`.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10686

namespace Problems.residue_thm

def ftc_const_add_right_half := @Problems.residue_thm.s10686

end Problems.residue_thm
