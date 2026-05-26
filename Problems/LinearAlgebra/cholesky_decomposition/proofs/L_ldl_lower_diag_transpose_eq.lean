import Mathlib
import Problems.LinearAlgebra.cholesky_decomposition.Defs

namespace Problems.LinearAlgebra.cholesky_decomposition

-- entry_kind: Builder
-- ldl_lower_diag_transpose_eq: LDL.lower_conj_diag + conjTranspose=transpose over ℝ closes L*D*Lᵀ=A
theorem ldl_lower_diag_transpose_eq {n : ℕ} {A : Matrix (Fin n) (Fin n) ℝ}
    (hA : A.PosDef) :
    LDL.lower hA * LDL.diag hA * (LDL.lower hA).transpose = A := by
  have h := LDL.lower_conj_diag hA
  simp only [Matrix.conjTranspose, Matrix.transpose] at h
  exact h

end Problems.LinearAlgebra.cholesky_decomposition
