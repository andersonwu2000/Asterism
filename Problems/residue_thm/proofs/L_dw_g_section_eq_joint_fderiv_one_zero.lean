-- Chain rule for τ-section of the joint smooth `g(p) = f(H p.1 p.2) · ∂_t H @ p (0,1)`.
-- Sub-goal `g_joint_diff_within_at_icc` packages the joint `DifferentiableWithinAt` on
-- `Icc×Icc`; once obtained, `HasFDerivWithinAt.comp_hasDerivWithinAt` against the section
-- embedding `τ' ↦ (τ', t)` (derivative `(1,0)`) plus `uniqueDiffOn_Icc_zero_one` give the
-- pointwise `derivWithin = fderivWithin · (1,0)` identity.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10397

namespace Problems.residue_thm

def dw_g_section_eq_joint_fderiv_one_zero := @Problems.residue_thm.s10397

end Problems.residue_thm
