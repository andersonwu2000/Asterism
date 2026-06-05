-- Apply `ih` to the leading n×n block A = (reindexed M).toBlocks₁₁.
-- ih needs (1) A Hermitian and (2) all leading principal minors of A positive.
--   • block_hermitian   — A is Hermitian (submatrix of a Hermitian matrix);
--   • block_minors_pos  — each leading minor of A equals a leading minor of M (> 0).
import Mathlib
import Problems.LinearAlgebra.sylvester_criterion.Defs
import Problems.LinearAlgebra.sylvester_criterion.proofs._strategy_s11607

namespace Problems.LinearAlgebra.sylvester_criterion

def leading_block_posdef := @Problems.LinearAlgebra.sylvester_criterion.s11607

end Problems.LinearAlgebra.sylvester_criterion
