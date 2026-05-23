import Mathlib
import Problems.LinearAlgebra.qr_decomposition.Defs

namespace Problems.LinearAlgebra.qr_decomposition

-- qt_mul_entry_eq_inner: expands (Qᵀ * A)[i,j] via Matrix.mul_apply and rewrites the
-- inner product via PiLp.inner_apply + norm_num [inner] to match the pointwise sum.
-- entry_kind: Builder
theorem qt_mul_entry_eq_inner {n : ℕ}
    (A : Matrix (Fin n) (Fin n) ℝ)
    (q : Fin n → EuclideanSpace ℝ (Fin n))
    (i j : Fin n) :
    ((Matrix.of fun i j => q j i).transpose * A) i j
      = inner (𝕜 := ℝ) (q i) ((EuclideanSpace.equiv (Fin n) ℝ).symm (A.transpose j)) := by
  simp only [Matrix.mul_apply, Matrix.transpose_apply, Matrix.of_apply]
  rw [PiLp.inner_apply]
  congr 1
  ext x
  simp only [EuclideanSpace.equiv, PiLp.continuousLinearEquiv_symm_apply,
             Matrix.transpose_apply]
  norm_num [inner]
  ring

end Problems.LinearAlgebra.qr_decomposition