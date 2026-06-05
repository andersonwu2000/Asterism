-- Schur complement (1×1) has positive determinant via the block-determinant factorization.
-- det M = det(toBlocks₁₁) · det(Schur) (schur_det_factor, using hHerm to rewrite toBlocks₂₁ =
-- toBlocks₁₂ᴴ); det M > 0 (mdet_pos, the last leading minor) and det(toBlocks₁₁) > 0 (hApd.det_pos)
-- force det(Schur) > 0. Each piece is strictly simpler: a scalar positivity (mdet_pos) and a
-- determinant identity (schur_det_factor); the final step is one scalar division (nlinarith).
import Mathlib
import Problems.LinearAlgebra.sylvester_criterion.Defs
import Problems.LinearAlgebra.sylvester_criterion.proofs._strategy_s11611

namespace Problems.LinearAlgebra.sylvester_criterion

def schur_det_pos := @Problems.LinearAlgebra.sylvester_criterion.s11611

end Problems.LinearAlgebra.sylvester_criterion
