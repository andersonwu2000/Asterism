import Mathlib
import Problems.LinearAlgebra.cholesky_decomposition.Defs
import Problems.LinearAlgebra.cholesky_decomposition.proofs.L_diag_sqrt_mul_self
import Problems.LinearAlgebra.cholesky_decomposition.proofs.L_ldl_lower_diag_transpose_eq

namespace Problems.LinearAlgebra.cholesky_decomposition

-- Decomposition: factor A = L D Lᵀ (`ldl_lower_diag_transpose_eq`) then split
-- D = Ds * Ds where Ds is the diagonal of √(diagEntries) (`diag_sqrt_mul_self`,
-- needs positivity for Real.sqrt_mul_self). Matrix algebra (transpose_mul +
-- diagonal_transpose + mul_assoc) rearranges to (L Ds)(L Ds)ᵀ.
theorem s11061 {n : ℕ} {A : Matrix (Fin n) (Fin n) ℝ}
    (hA : A.PosDef) (h_pos : ∀ i, 0 < LDL.diagEntries hA i) :
    A =
      (LDL.lower hA * Matrix.diagonal (fun i => Real.sqrt (LDL.diagEntries hA i))) *
        (LDL.lower hA *
          Matrix.diagonal (fun i => Real.sqrt (LDL.diagEntries hA i))).transpose  := by
  set Ds : Matrix (Fin n) (Fin n) ℝ :=
    Matrix.diagonal (fun i => Real.sqrt (LDL.diagEntries hA i)) with hDs
  have h_diag_sq : Ds * Ds = LDL.diag hA := diag_sqrt_mul_self hA h_pos
  have h_ldl_real :
      LDL.lower hA * LDL.diag hA * (LDL.lower hA).transpose = A :=
    ldl_lower_diag_transpose_eq hA
  calc A = LDL.lower hA * LDL.diag hA * (LDL.lower hA).transpose := h_ldl_real.symm
    _ = (LDL.lower hA * Ds) * (Ds * (LDL.lower hA).transpose) := by
          rw [← h_diag_sq]; simp only [Matrix.mul_assoc]
    _ = (LDL.lower hA * Ds) * (Ds.transpose * (LDL.lower hA).transpose) := by
          rw [Matrix.diagonal_transpose]
    _ = (LDL.lower hA * Ds) * (LDL.lower hA * Ds).transpose := by
          rw [Matrix.transpose_mul]

end Problems.LinearAlgebra.cholesky_decomposition
