-- `LDL.lower hA = (LDL.lowerInv hA)⁻¹`. Push BT through inversion via
-- `Matrix.blockTriangular_inv_of_blockTriangular`, then discharge BT of
-- `LDL.lowerInv` from `LDL.lowerInv_triangular` and a Nat-subtraction
-- monotonicity step (`(n-1)-j.val < (n-1)-i.val ↔ i.val < j.val` on `Fin n`).
import Mathlib
import Problems.LinearAlgebra.cholesky_decomposition.Defs
import Problems.LinearAlgebra.cholesky_decomposition.proofs._strategy_s11063

namespace Problems.LinearAlgebra.cholesky_decomposition

def ldl_lower_block_triangular := @Problems.LinearAlgebra.cholesky_decomposition.s11063

end Problems.LinearAlgebra.cholesky_decomposition
