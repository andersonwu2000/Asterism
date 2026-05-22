-- Decompose SVD into (1) existence of an eigenbasis `b_E` of E diagonalising
-- `T.adjoint ∘ₗ T` with eigenvalues `(T.singularValues i)^2`, and (2) the
-- construction of `b_F` and the diagonal-matrix equation from such a `b_E`.
-- Sub-goal 1 is the spectral-theorem step on the positive self-adjoint
-- operator `T†T`; sub-goal 2 builds `u_i := σ_i⁻¹ • T (b_E i)` for the
-- σ_i > 0 indices, completes to an orthonormal basis of F, then verifies
-- the matrix entries — both strictly simpler than the joint SVD claim.
import Mathlib
import Problems.LinearAlgebra.svd.Defs
import Problems.LinearAlgebra.svd.proofs._strategy_s10850

namespace Problems.LinearAlgebra.svd

def main := @Problems.LinearAlgebra.svd.s10850

end Problems.LinearAlgebra.svd
