import Mathlib
import Problems.LinearAlgebra.normal_diagonalization.Defs
import Problems.LinearAlgebra.normal_diagonalization.proofs.L_row_col_norm_eq
import Problems.LinearAlgebra.normal_diagonalization.proofs.L_triangular_rowcol_eq_imp_diag

namespace Problems.LinearAlgebra.normal_diagonalization

-- Upper-triangular + normal ⇒ diagonal, split into a normality-extraction
-- and the triangular induction crux.
--   * `row_col_norm_eq` — from `Commute Mᴴ M`, equate diagonal entries of MᴴM and
--     MMᴴ to get the column-vs-row squared-norm identity `∑‖M k i‖² = ∑‖M i k‖²`.
--   * `triangular_rowcol_eq_imp_diag` — pure crux: triangular + that norm identity
--     forces off-diagonal entries to zero (strong induction on the row).
-- They combine directly: feed `htri` and the norm identity into the matrix lemma.
theorem s11534 {n : ℕ} (M : Matrix (Fin n) (Fin n) ℂ)
    (htri : M.BlockTriangular id) (hcomm : Commute (Matrix.conjTranspose M) M) :
    M.IsDiag := by
  have h_rc : ∀ i, ∑ k, ‖M k i‖ ^ 2 = ∑ k, ‖M i k‖ ^ 2 := row_col_norm_eq M hcomm
  exact triangular_rowcol_eq_imp_diag M htri h_rc

end Problems.LinearAlgebra.normal_diagonalization
