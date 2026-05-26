import Mathlib
import Problems.LinearAlgebra.cholesky_decomposition.Defs

namespace Problems.LinearAlgebra.cholesky_decomposition

-- entry_kind: Builder
-- diag_sqrt_mul_self: diagonal of sqrt entries squared equals LDL.diag via mul_self_sqrt
theorem diag_sqrt_mul_self {n : ℕ} {A : Matrix (Fin n) (Fin n) ℝ}
    (hA : A.PosDef) (h_pos : ∀ i, 0 < LDL.diagEntries hA i) :
    Matrix.diagonal (fun i => Real.sqrt (LDL.diagEntries hA i)) *
      Matrix.diagonal (fun i => Real.sqrt (LDL.diagEntries hA i)) =
      LDL.diag hA := by
  simp only [LDL.diag, Matrix.diagonal_mul_diagonal]
  congr 1
  ext i
  exact Real.mul_self_sqrt (le_of_lt (h_pos i))

end Problems.LinearAlgebra.cholesky_decomposition

