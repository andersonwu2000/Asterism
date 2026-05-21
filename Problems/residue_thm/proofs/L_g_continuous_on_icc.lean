-- ContinuousOn (f ∘ H τ * ∂_τ' H(·,t)) on Icc 0 1 via ContinuousOn.mul.
-- (1) f_h_continuous_on_icc: continuity of f ∘ H τ on Icc — composition of analytic f
--     with the C² slice H τ, mapped into V; pure Builder leaf.
-- (2) partial_tau_h_continuous_on_icc: continuity of the τ-partial derivative slice
--     `t ↦ derivWithin (H · t) (Icc 0 1) τ` on Icc — from C² of the joint H, the partial
--     in τ is a continuous function of (τ,t) on the closed square; Backward.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10338

namespace Problems.residue_thm

def g_continuous_on_icc := @Problems.residue_thm.s10338

end Problems.residue_thm
