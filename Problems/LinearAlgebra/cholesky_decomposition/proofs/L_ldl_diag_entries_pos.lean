-- Direct sorry-free closure: PosDef preservation under invertible conjugation +
-- diagonal characterisation. `LDL.diag hA = Lᴴ⁻¹·A·L⁻¹` is PosDef because A is
-- and `LDL.lowerInv hA` is invertible (so vecMul-by-it is injective); a PosDef
-- diagonal matrix has each entry strictly positive via `posDef_diagonal_iff`.
import Mathlib
import Problems.LinearAlgebra.cholesky_decomposition.Defs
import Problems.LinearAlgebra.cholesky_decomposition.proofs._strategy_s11062

namespace Problems.LinearAlgebra.cholesky_decomposition

def ldl_diag_entries_pos := @Problems.LinearAlgebra.cholesky_decomposition.s11062

end Problems.LinearAlgebra.cholesky_decomposition
