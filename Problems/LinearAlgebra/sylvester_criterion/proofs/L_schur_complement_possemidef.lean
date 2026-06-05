-- Schur complement (1×1) is PosSemidef via its determinant.
-- The 1-dim Schur complement S = D - Bᴴ A⁻¹ B has 0 < S.det (schur_det_pos:
-- det of the reindexed M factors as det A · det S, both numerator and det A > 0),
-- and for a Fin 1 matrix positive determinant gives PosSemidef
-- (possemidef_of_det_pos_fin_one). Each piece is strictly simpler: the det bound
-- is a scalar inequality, the Fin 1 upgrade is dimension-free.
import Mathlib
import Problems.LinearAlgebra.sylvester_criterion.Defs
import Problems.LinearAlgebra.sylvester_criterion.proofs._strategy_s11606

namespace Problems.LinearAlgebra.sylvester_criterion

def schur_complement_possemidef := @Problems.LinearAlgebra.sylvester_criterion.s11606

end Problems.LinearAlgebra.sylvester_criterion
