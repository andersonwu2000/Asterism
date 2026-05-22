-- Split the one-step T-invariant extension into (A) producing a quotient-eigenvector
-- lift `v ∉ U` with `T v - μ • v ∈ U` for some μ — this is where IsAlgClosed enters,
-- via the induced endomorphism on V/U having an eigenvalue — and (B) a pure
-- linear-algebra step that turns any such (v, μ) into `U' = U ⊔ span{v}`,
-- T-invariant of dim `finrank U + 1`. Sub-goal (B) is alg-closed-free.
import Mathlib
import Problems.LinearAlgebra.schur_triangularization.Defs
import Problems.LinearAlgebra.schur_triangularization.proofs._strategy_s10839

namespace Problems.LinearAlgebra.schur_triangularization

def extend_invariant_subspace := @Problems.LinearAlgebra.schur_triangularization.s10839

end Problems.LinearAlgebra.schur_triangularization
