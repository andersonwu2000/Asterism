-- Upper-triangular + the column/row squared-norm identity ⇒ diagonal, by strong
-- induction on the row value with two abstract, strictly-smaller sub-lemmas.
--   * Combinator: strong induction on `i.val` (`Nat.strong_induction_on`) supplies, at
--     row `i`, that every earlier row is already diagonal (`ihrows`).
--   * `col_sum_collapse` — column `i`'s squared-norm sum collapses to `‖M i i‖²`
--     (earlier rows + triangularity kill every off-diagonal entry). A plain ℝ-sum
--     identity, not `IsDiag`.
--   * `sum_norm_sq_eq_single_imp_zero` — an abstract vector fact: if `∑ ‖f k‖²` equals
--     its `i`-th term, every other `f k` vanishes. No matrix in sight.
--   Glue: feed `hcol` through `hsum i` to get the row sum `= ‖M i i‖²`, then the vector
--   lemma forces row `i`'s off-diagonal entries to zero.
import Mathlib
import Problems.LinearAlgebra.normal_diagonalization.Defs
import Problems.LinearAlgebra.normal_diagonalization.proofs._strategy_s11545

namespace Problems.LinearAlgebra.normal_diagonalization

def triangular_rowcol_eq_imp_diag := @Problems.LinearAlgebra.normal_diagonalization.s11545

end Problems.LinearAlgebra.normal_diagonalization
