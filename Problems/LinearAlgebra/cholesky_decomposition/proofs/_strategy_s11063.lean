import Mathlib
import Problems.LinearAlgebra.cholesky_decomposition.Defs

namespace Problems.LinearAlgebra.cholesky_decomposition

-- `LDL.lower hA = (LDL.lowerInv hA)⁻¹`. Push BT through inversion via
-- `Matrix.blockTriangular_inv_of_blockTriangular`, then discharge BT of
-- `LDL.lowerInv` from `LDL.lowerInv_triangular` and a Nat-subtraction
-- monotonicity step (`(n-1)-j.val < (n-1)-i.val ↔ i.val < j.val` on `Fin n`).
theorem s11063 {n : ℕ} {A : Matrix (Fin n) (Fin n) ℝ}
    (hA : A.PosDef) :
    (LDL.lower hA).BlockTriangular (fun i : Fin n => (n - 1 : ℕ) - (i : ℕ))  := by
  have hinv : Invertible (LDL.lowerInv hA) := LDL.invertibleLowerInv hA
  refine Matrix.blockTriangular_inv_of_blockTriangular ?_
  intro i j hij
  simp only at hij
  apply LDL.lowerInv_triangular hA
  have hi : i.val < n := i.isLt
  have hj : j.val < n := j.isLt
  change i.val < j.val
  omega

end Problems.LinearAlgebra.cholesky_decomposition
