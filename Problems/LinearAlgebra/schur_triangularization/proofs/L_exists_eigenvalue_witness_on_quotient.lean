-- Descend `T` to `F : V ⧸ U →ₗ[K] V ⧸ U` via `Submodule.mapQ` (using
-- `U`-invariance recast as `U ≤ comap T U`), apply `Module.End.exists_eigenvalue`
-- to the finite-dimensional nontrivial `V ⧸ U` over the algebraically closed `K`
-- to obtain `(μ, w)` with `F w = μ • w` and `w ≠ 0`, then lift `w` along
-- `U.mkQ_surjective` to `v ∈ V` and translate via `Submodule.mapQ_apply`.
import Mathlib
import Problems.LinearAlgebra.schur_triangularization.Defs
import Problems.LinearAlgebra.schur_triangularization.proofs._strategy_s10846

namespace Problems.LinearAlgebra.schur_triangularization

def exists_eigenvalue_witness_on_quotient := @Problems.LinearAlgebra.schur_triangularization.s10846

end Problems.LinearAlgebra.schur_triangularization
