-- Schur complement preserves nonsingularity of leading principal minors:
--   1. `a11_ne_zero` — pivot `A 0 0 ≠ 0` from the `k = 1` minor hypothesis.
--   2. `schur_minor_factor` — for each `k ≤ n`, the `(k+1)×(k+1)` leading minor
--      of `A` factors as `A 0 0 * det(S_k)` (Schur complement determinant identity
--      applied to the leading submatrix).
-- Combine: `det(A_{k+1}) ≠ 0` (from `hPM`) and `det(A_{k+1}) = A 0 0 * det(S_k)`
-- force `det(S_k) ≠ 0` by field cancellation.
import Mathlib
import Problems.LinearAlgebra.lu_decomposition.Defs
import Problems.LinearAlgebra.lu_decomposition.proofs._strategy_s11324

namespace Problems.LinearAlgebra.lu_decomposition

def schur_complement_minors := @Problems.LinearAlgebra.lu_decomposition.s11324

end Problems.LinearAlgebra.lu_decomposition
