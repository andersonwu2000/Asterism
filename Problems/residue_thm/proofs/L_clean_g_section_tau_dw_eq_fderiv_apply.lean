-- Section chain rule: differentiate the τ'-slice `τ' ↦ g(τ', t)` of the joint
-- cleaned product `g(p) = f(H p.1 p.2) * fderivWithin H_joint (Icc×Icc) p (0,1)`
-- by composing the joint `HasFDerivWithinAt` at `(τ, t)` with the section embedding
-- `τ' ↦ (τ', t)` (whose derivative is `(1, 0)`), then closing via
-- `HasDerivWithinAt.derivWithin` over `uniqueDiffOn_Icc_zero_one`. Sole sub-goal
-- `g_joint_diff_within_icc` supplies `DifferentiableWithinAt ℝ g (Icc×Icc) (τ, t)`
-- — derivable from `clean_g_joint_contdiff_one`'s `ContDiffOn ℝ 1`.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10391

namespace Problems.residue_thm

def clean_g_section_tau_dw_eq_fderiv_apply := @Problems.residue_thm.s10391

end Problems.residue_thm
