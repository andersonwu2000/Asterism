-- Upper-triangular + normal ⇒ diagonal, split into a normality-extraction
-- and the triangular induction crux.
--   * `row_col_norm_eq` — from `Commute Mᴴ M`, equate diagonal entries of MᴴM and
--     MMᴴ to get the column-vs-row squared-norm identity `∑‖M k i‖² = ∑‖M i k‖²`.
--   * `triangular_rowcol_eq_imp_diag` — pure crux: triangular + that norm identity
--     forces off-diagonal entries to zero (strong induction on the row).
-- They combine directly: feed `htri` and the norm identity into the matrix lemma.
import Mathlib
import Problems.LinearAlgebra.normal_diagonalization.Defs
import Problems.LinearAlgebra.normal_diagonalization.proofs._strategy_s11534

namespace Problems.LinearAlgebra.normal_diagonalization

def matrix_core := @Problems.LinearAlgebra.normal_diagonalization.s11534

end Problems.LinearAlgebra.normal_diagonalization
