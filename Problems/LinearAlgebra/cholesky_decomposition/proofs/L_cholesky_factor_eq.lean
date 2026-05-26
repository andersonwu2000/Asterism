-- Decomposition: factor A = L D Lᵀ (`ldl_lower_diag_transpose_eq`) then split
-- D = Ds * Ds where Ds is the diagonal of √(diagEntries) (`diag_sqrt_mul_self`,
-- needs positivity for Real.sqrt_mul_self). Matrix algebra (transpose_mul +
-- diagonal_transpose + mul_assoc) rearranges to (L Ds)(L Ds)ᵀ.
import Mathlib
import Problems.LinearAlgebra.cholesky_decomposition.Defs
import Problems.LinearAlgebra.cholesky_decomposition.proofs._strategy_s11061

namespace Problems.LinearAlgebra.cholesky_decomposition

def cholesky_factor_eq := @Problems.LinearAlgebra.cholesky_decomposition.s11061

end Problems.LinearAlgebra.cholesky_decomposition
