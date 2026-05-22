-- Decompose into: (1) T†T is symmetric, and (2) the eigenvector basis of
-- T†T (from IsSymmetric.eigenvectorBasis) has eigenvalues equal to
-- (T.singularValues i)^2 — the spectral-theorem identification step.
-- The combinator threads (1) into IsSymmetric.eigenvectorBasis to produce
-- the witness, then applies (2) for the diagonalisation property.
import Mathlib
import Problems.LinearAlgebra.svd.Defs
import Problems.LinearAlgebra.svd.proofs._strategy_s10851

namespace Problems.LinearAlgebra.svd

def eigenbasis_t_adjoint_t := @Problems.LinearAlgebra.svd.s10851

end Problems.LinearAlgebra.svd
