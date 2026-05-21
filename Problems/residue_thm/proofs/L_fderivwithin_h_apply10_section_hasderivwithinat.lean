-- Section chain rule for the partial in (1,0) direction: decompose into
-- `HasFDerivWithinAt.comp_hasDerivWithinAt` with the section embedding
-- `t' ↦ (τ, t')`. Sub-goal `fderivwithin_apply10_hasfderivwithinat` supplies
-- the joint Fréchet differentiability of `p ↦ fderivWithin H' s p (1,0)` at
-- `(τ, t)` with derivative `(fderivWithin (fderivWithin H' s) s (τ,t)).flip (1,0)`;
-- the section embedding has derivative `(0,1)` and the inner apply collapses
-- via `ContinuousLinearMap.flip_apply` to the goal's iterated form.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10396

namespace Problems.residue_thm

def fderivwithin_h_apply10_section_hasderivwithinat := @Problems.residue_thm.s10396

end Problems.residue_thm
