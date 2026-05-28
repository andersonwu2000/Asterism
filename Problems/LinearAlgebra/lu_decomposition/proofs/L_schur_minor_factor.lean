-- Reduce the leading-minor Schur factorization to its index-free shape.
-- Set `M` to the (k+1)-leading principal submatrix of `A`; then the goal is the
-- generic identity `det M = M 0 0 * det (Schur M)`. After `rw`-substituting that,
-- `congr 1` closes the residual matrix equality because `Fin.castLE _ i.succ` and
-- `(Fin.castLE _ i).succ` agree by `Fin.val`.
import Mathlib
import Problems.LinearAlgebra.lu_decomposition.Defs
import Problems.LinearAlgebra.lu_decomposition.proofs._strategy_s11326

namespace Problems.LinearAlgebra.lu_decomposition

def schur_minor_factor := @Problems.LinearAlgebra.lu_decomposition.s11326

end Problems.LinearAlgebra.lu_decomposition
