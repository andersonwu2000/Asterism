import Mathlib
import Problems.LinearAlgebra.sylvester_criterion.Defs
import Problems.LinearAlgebra.sylvester_criterion.proofs.L_block_hermitian
import Problems.LinearAlgebra.sylvester_criterion.proofs.L_block_minors_pos

namespace Problems.LinearAlgebra.sylvester_criterion

-- Apply `ih` to the leading n×n block A = (reindexed M).toBlocks₁₁.
-- ih needs (1) A Hermitian and (2) all leading principal minors of A positive.
--   • block_hermitian   — A is Hermitian (submatrix of a Hermitian matrix);
--   • block_minors_pos  — each leading minor of A equals a leading minor of M (> 0).
theorem s11607 {n : ℕ}
    (ih : ∀ (M : Matrix (Fin n) (Fin n) ℝ), M.IsHermitian →
      (∀ (k : Fin n), 0 < leadingPrincipalMinor M k) → M.PosDef)
    (M : Matrix (Fin (n + 1)) (Fin (n + 1)) ℝ)
    (hHerm : M.IsHermitian)
    (hMinors : ∀ (k : Fin (n + 1)), 0 < leadingPrincipalMinor M k) :
    (M.submatrix (finSumFinEquiv (m := n) (n := 1))
      (finSumFinEquiv (m := n) (n := 1))).toBlocks₁₁.PosDef  := by
  have h_herm := block_hermitian M hHerm
  have h_minors := block_minors_pos M hMinors
  exact ih _ h_herm h_minors

end Problems.LinearAlgebra.sylvester_criterion
