-- `P.IsSymmetric ↔ (P.toMatrix b_E b_E).IsHermitian` for an orthonormal basis
-- (`LinearMap.isHermitian_toMatrix_iff`); rewrite into the concrete matrix world,
-- where the matrix of the diagonal map P : b_E i ↦ σ_i • b_E i is diagonal with real
-- entries σ_i, hence Hermitian — a finite, computational `ext`-check, strictly more
-- concrete than the inner-product symmetry statement.
import Mathlib
import Problems.LinearAlgebra.polar_decomposition.Defs
import Problems.LinearAlgebra.polar_decomposition.proofs._strategy_s11552

namespace Problems.LinearAlgebra.polar_decomposition

def p_symmetric := @Problems.LinearAlgebra.polar_decomposition.s11552

end Problems.LinearAlgebra.polar_decomposition
