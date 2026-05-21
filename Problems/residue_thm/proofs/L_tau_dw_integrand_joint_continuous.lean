-- Sliced version of s10357: rewrite τ-`derivWithin` of the product
-- `f∘H · ∂_t H` as the partial of the joint smooth function
-- `g(q) = f(H q.1 q.2) · fderivWithin (H ·.1 ·.2) at (q,(0,1))` in
-- direction (1,0); joint continuity transports back via `ContinuousOn.congr`.
-- Sub-goal `tau_dw_eq_fderiv_apply_on_icc_prod` is the pointwise equality on
-- `Icc×Icc`; `fderiv_apply_continuous_on_icc_prod` is joint continuity of the
-- fderivWithin side. Combinator: `h_cont.congr h_eq`.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10392

namespace Problems.residue_thm

def tau_dw_integrand_joint_continuous := @Problems.residue_thm.s10392

end Problems.residue_thm
