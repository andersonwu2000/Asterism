import Mathlib
import Problems.LinearAlgebra.qr_decomposition.Defs
import Problems.LinearAlgebra.qr_decomposition.proofs.L_block_triangular_qt_mul_of_span
import Problems.LinearAlgebra.qr_decomposition.proofs.L_gram_schmidt_ortho_triangular_span
import Problems.LinearAlgebra.qr_decomposition.proofs.L_matrix_of_orthonormal_cols_orthogonal

namespace Problems.LinearAlgebra.qr_decomposition

-- Gram-Schmidt-based decomposition:
--   (1) gram_schmidt_ortho_triangular_span: LI columns of A yield an orthonormal q in
--       EuclideanSpace whose initial-segment span contains each column.
--   (2) matrix_of_orthonormal_cols_orthogonal: orthonormal q gives Q with Q * Qᵀ = 1.
--   (3) block_triangular_qt_mul_of_span: the span condition makes Qᵀ * A upper triangular.
-- Combinator: extract q from (1), build Q := Matrix.of (fun i j => q j i), close with (2)/(3).
theorem s10883 {n : ℕ}
    (A : Matrix (Fin n) (Fin n) ℝ) :
    LinearIndependent ℝ A.transpose →
    ∃ Q : Matrix (Fin n) (Fin n) ℝ,
      Q * Matrix.transpose Q = 1 ∧ (Matrix.transpose Q * A).BlockTriangular id  := by
  intro hLI
  obtain ⟨q, hq_orth, hq_span⟩ :=
    gram_schmidt_ortho_triangular_span A hLI
  refine ⟨Matrix.of fun i j => q j i, ?_, ?_⟩
  · exact matrix_of_orthonormal_cols_orthogonal q hq_orth
  · exact block_triangular_qt_mul_of_span A q hq_orth hq_span

end Problems.LinearAlgebra.qr_decomposition
