import Mathlib
import Problems.LinearAlgebra.qr_decomposition.Defs
import Problems.LinearAlgebra.qr_decomposition.proofs.L_orthogonal_upper_triangularizer

namespace Problems.LinearAlgebra.qr_decomposition

-- Reduce QR existence to "orthogonal Q with Qᵀ*A upper-triangular":
-- pick R := Qᵀ*A; the equation A = Q*R follows from Q*Qᵀ = 1.
theorem s10881 : ∀ {n : ℕ} (A : Matrix (Fin n) (Fin n) ℝ),
  A.det ≠ 0 →
  ∃ (Q R : Matrix (Fin n) (Fin n) ℝ),
    Q * Matrix.transpose Q = 1 ∧
    R.BlockTriangular id ∧
    A = Q * R  := by
  intro n A hA
  have h_orth := orthogonal_upper_triangularizer A hA
  obtain ⟨Q, hQ, hR⟩ := h_orth
  refine ⟨Q, Matrix.transpose Q * A, hQ, hR, ?_⟩
  rw [← Matrix.mul_assoc, hQ, Matrix.one_mul]

end Problems.LinearAlgebra.qr_decomposition
