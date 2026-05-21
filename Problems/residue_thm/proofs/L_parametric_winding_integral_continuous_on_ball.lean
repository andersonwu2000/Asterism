-- Decompose parametric integral continuity by swapping `deriv γ` for
-- `derivWithin γ (Icc 0 1)` a.e. on [0,1] (junk at endpoints, see LESSONS),
-- proving continuity of the cleaner derivWithin-integral, then transporting
-- back via `ContinuousOn.congr`.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10593

namespace Problems.residue_thm

def parametric_winding_integral_continuous_on_ball := @Problems.residue_thm.s10593

end Problems.residue_thm
