-- Direct application of Mathlib's Schwarz symmetry: `ContDiffWithinAt.isSymmSndFDerivWithinAt`.
-- The point `(τ, t)` lies in `closure (interior (Icc×Icc)) = closure (Ioo×Ioo) = Icc×Icc`,
-- and `hH` supplies `ContDiffWithinAt ℝ 2` there; `UniqueDiffOn` on the product follows
-- from `uniqueDiffOn_Icc_zero_one.prod`. Conclude via `IsSymmSndFDerivWithinAt.eq`.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10395

namespace Problems.residue_thm

def mixed_partial_schwarz_swap := @Problems.residue_thm.s10395

end Problems.residue_thm
