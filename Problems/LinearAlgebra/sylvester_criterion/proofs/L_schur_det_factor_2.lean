-- Schur block-determinant factorization: rewrite M.det as the det of the
-- finSumFinEquiv-reindexed matrix (det_submatrix_equiv_self), expand via
-- fromBlocks_toBlocks + det_fromBlocks₁₁ (Invertible toBlocks₁₁ from hApd),
-- then replace toBlocks₂₁ with toBlocks₁₂ᴴ via the sole sub-goal
-- block_conjtranspose_factor (needs hHerm); ⅟ → ⁻¹ closes the gap.
import Mathlib
import Problems.LinearAlgebra.sylvester_criterion.Defs
import Problems.LinearAlgebra.sylvester_criterion.proofs._strategy_s11612

namespace Problems.LinearAlgebra.sylvester_criterion

def schur_det_factor_2 := @Problems.LinearAlgebra.sylvester_criterion.s11612

end Problems.LinearAlgebra.sylvester_criterion
