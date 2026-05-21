-- Decompose into joint C¹ smoothness of the (τ, t)-extended integrand on `Icc×Icc`
-- (replacing the inner `derivWithin (H τ') (Icc 0 1) t` with `fderivWithin H_joint
-- (Icc×Icc) p (0,1)`) plus the pointwise identity equating the τ-section derivWithin
-- to fderivWithin in direction (1,0). Continuity of the τ-slice falls out of
-- `ContDiffOn.continuousOn_fderivWithin` composed with the τ-slice map and CLM eval.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10349

namespace Problems.residue_thm

def x_clean_continuous_on_icc := @Problems.residue_thm.s10349

end Problems.residue_thm
