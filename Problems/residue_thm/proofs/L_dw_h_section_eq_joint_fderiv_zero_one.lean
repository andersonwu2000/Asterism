-- Direct one-step proof per lesson 34: compose joint `HasFDerivWithinAt` with the
-- `t' ↦ (τ, t')` section's `HasDerivWithinAt (0,1)`, then `.derivWithin` against
-- `uniqueDiffOn_Icc_zero_one`. No sub-goals required (framework leaf-bypass).
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10398

namespace Problems.residue_thm

def dw_h_section_eq_joint_fderiv_zero_one := @Problems.residue_thm.s10398

end Problems.residue_thm
