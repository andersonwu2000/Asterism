-- Direct one-shot: assemble C¹ regularity of the joint integrand
-- g(q) = f(H q.1 q.2) · fderivWithin H_joint q (0,1) on Icc×Icc, then take its
-- fderivWithin (continuous via ContDiffOn.continuousOn_fderivWithin on the
-- unique-diff product set), evaluate at the constant vector (1,0) via
-- ContinuousOn.clm_apply, and precompose with the continuous coordinate swap
-- p ↦ (p.2, p.1) (which is MapsTo Icc×Icc → Icc×Icc).
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10363

namespace Problems.residue_thm

def fderiv_apply_continuous_on_icc_prod := @Problems.residue_thm.s10363

end Problems.residue_thm
