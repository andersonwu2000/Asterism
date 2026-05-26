import Mathlib
import Problems.LinearAlgebra.cholesky_decomposition.Defs

namespace Problems.LinearAlgebra.cholesky_decomposition

-- Direct sorry-free closure: PosDef preservation under invertible conjugation +
-- diagonal characterisation. `LDL.diag hA = Lᴴ⁻¹·A·L⁻¹` is PosDef because A is
-- and `LDL.lowerInv hA` is invertible (so vecMul-by-it is injective); a PosDef
-- diagonal matrix has each entry strictly positive via `posDef_diagonal_iff`.
theorem s11062 {n : ℕ} {A : Matrix (Fin n) (Fin n) ℝ}
    (hA : A.PosDef) :
    ∀ i, 0 < LDL.diagEntries hA i  := by
  have h_inv : Invertible (LDL.lowerInv hA) := LDL.invertibleLowerInv hA
  have h_inj : Function.Injective
      (fun v : Fin n → ℝ => Matrix.vecMul v (LDL.lowerInv hA)) :=
    Matrix.vecMul_injective_of_invertible (LDL.lowerInv hA)
  have h_diag_posdef : (LDL.diag hA).PosDef := by
    rw [LDL.diag_eq_lowerInv_conj]
    exact hA.mul_mul_conjTranspose_same h_inj
  intro i
  have h_eq : LDL.diag hA = Matrix.diagonal (LDL.diagEntries hA) := rfl
  rw [h_eq] at h_diag_posdef
  exact (Matrix.posDef_diagonal_iff.mp h_diag_posdef) i

end Problems.LinearAlgebra.cholesky_decomposition
