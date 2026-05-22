-- Direct: apply `IsSymmetric.apply_eigenvectorBasis` (eigenvalue scalar form),
-- then identify the eigenvalue with `(T.singularValues i)^2` via `sq_singularValues_fin`.
import Mathlib
import Problems.LinearAlgebra.svd.Defs
import Problems.LinearAlgebra.svd.proofs._strategy_s10853

namespace Problems.LinearAlgebra.svd

def eigenbasis_apply_eq_sq_singular_values := @Problems.LinearAlgebra.svd.s10853

end Problems.LinearAlgebra.svd
