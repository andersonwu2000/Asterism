-- Lift the τ-derivative `deriv (H τ) t` from a pointwise question at a single x
-- to ContDiffOn of the joint (τ, t) map on the open interior square.
-- Sub-goal `partial_t_h_contdiffon_ioo` packages the analytical content
-- (C¹ regularity of the t-partial as a function of (τ, t)); closing here is
-- a routine open-set restriction + composition with the C∞ slice τ ↦ (τ, t).
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10341

namespace Problems.residue_thm

def deriv_h_diff_in_tau := @Problems.residue_thm.s10341

end Problems.residue_thm
