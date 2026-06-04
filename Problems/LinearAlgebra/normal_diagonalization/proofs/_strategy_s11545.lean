import Mathlib
import Problems.LinearAlgebra.normal_diagonalization.Defs
import Problems.LinearAlgebra.normal_diagonalization.proofs.L_col_sum_collapse
import Problems.LinearAlgebra.normal_diagonalization.proofs.L_sum_norm_sq_eq_single_imp_zero

namespace Problems.LinearAlgebra.normal_diagonalization

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
theorem s11545 {n : ℕ} (M : Matrix (Fin n) (Fin n) ℂ)
    (htri : M.BlockTriangular id)
    (hsum : ∀ i, ∑ k, ‖M k i‖ ^ 2 = ∑ k, ‖M i k‖ ^ 2) :
    M.IsDiag  := by
  have aux : ∀ m : ℕ, ∀ i : Fin n, i.val = m → ∀ k : Fin n, i ≠ k → M i k = 0 := by
    intro m
    induction m using Nat.strong_induction_on with
    | _ m ih =>
      intro i hi k hik
      have ihrows : ∀ j : Fin n, j < i → ∀ k' : Fin n, j ≠ k' → M j k' = 0 :=
        fun j hj k' hjk' => ih j.val ((Fin.lt_def.mp hj).trans_eq hi) j rfl k' hjk'
      have hcol : ∑ k, ‖M k i‖ ^ 2 = ‖M i i‖ ^ 2 := col_sum_collapse M htri i ihrows
      have hrow : ∑ k, ‖M i k‖ ^ 2 = ‖M i i‖ ^ 2 := by rw [← hsum i]; exact hcol
      exact sum_norm_sq_eq_single_imp_zero (fun k => M i k) i hrow k (Ne.symm hik)
  intro i j hij
  exact aux i.val i rfl j hij
end Problems.LinearAlgebra.normal_diagonalization
