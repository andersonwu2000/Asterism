-- Decomposition: rewrite the τ-section derivWithin as the (1,0)-application of the joint
-- fderivWithin, then leverage joint continuity of `fderivWithin` (from C² of the uncurried H).
-- Sub-goal `partial_tau_eq_fderiv_apply` is a pointwise derivative identity (Builder).
-- Joint fderivWithin continuity is a one-liner via `ContDiffOn.continuousOn_fderivWithin`,
-- composed with the τ-slice map and CLM evaluation at (1,0).
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10344

namespace Problems.residue_thm

def partial_tau_h_continuous_on_icc := @Problems.residue_thm.s10344

end Problems.residue_thm
