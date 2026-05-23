-- Gram-Schmidt-based decomposition:
--   (1) gram_schmidt_ortho_triangular_span: LI columns of A yield an orthonormal q in
--       EuclideanSpace whose initial-segment span contains each column.
--   (2) matrix_of_orthonormal_cols_orthogonal: orthonormal q gives Q with Q * Qᵀ = 1.
--   (3) block_triangular_qt_mul_of_span: the span condition makes Qᵀ * A upper triangular.
-- Combinator: extract q from (1), build Q := Matrix.of (fun i j => q j i), close with (2)/(3).
import Mathlib
import Problems.LinearAlgebra.qr_decomposition.Defs
import Problems.LinearAlgebra.qr_decomposition.proofs._strategy_s10883

namespace Problems.LinearAlgebra.qr_decomposition

def orthogonal_upper_triangularizer_of_lin_indep_columns := @Problems.LinearAlgebra.qr_decomposition.s10883

end Problems.LinearAlgebra.qr_decomposition
