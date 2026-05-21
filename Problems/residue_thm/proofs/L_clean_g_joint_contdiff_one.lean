-- Split the C¹ product into its two factors and recombine via `ContDiffOn.mul`.
-- (1) `f_h_joint_contdiff_one`: `f ∘ H` is C¹ on `Icc×Icc`.
-- (2) `fderivwithin_joint_contdiff_one`: the within-derivative of `H` evaluated at
--     `(0,1)` is C¹ on `Icc×Icc` (`ContDiffOn.fderivWithin` on the unique-diff
--     product set, then post-composed with the linear evaluation at `(0,1)`).
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10358

namespace Problems.residue_thm

def clean_g_joint_contdiff_one := @Problems.residue_thm.s10358

end Problems.residue_thm
