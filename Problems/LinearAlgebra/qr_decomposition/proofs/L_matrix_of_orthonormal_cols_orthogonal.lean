import Mathlib
import Problems.LinearAlgebra.qr_decomposition.Defs

namespace Problems.LinearAlgebra.qr_decomposition

-- entry_kind: Builder
-- matrix_of_orthonormal_cols_orthogonal: orthonormal columns give Q * Qᵀ = I
-- via showing Qᵀ * Q = I entry-wise (inner product) then using square commutativity
theorem matrix_of_orthonormal_cols_orthogonal {n : ℕ}
    (q : Fin n → EuclideanSpace ℝ (Fin n)) :
    Orthonormal ℝ q →
    (Matrix.of fun i j => q j i) * (Matrix.of fun i j => q j i).transpose
      = (1 : Matrix (Fin n) (Fin n) ℝ) := by
  intro h
  have hQtQ : (Matrix.of fun i j => q j i).transpose *
              (Matrix.of fun i j => q j i) = 1 := by
    ext i j
    simp only [Matrix.mul_apply, Matrix.transpose_apply, Matrix.of_apply, Matrix.one_apply]
    have horth := orthonormal_iff_ite.mp h i j
    rw [← horth]
    simp only [PiLp.inner_apply]
    congr 1; ext x
    simp [Inner.inner, mul_comm]
  exact mul_eq_one_comm.mpr hQtQ

end Problems.LinearAlgebra.qr_decomposition
