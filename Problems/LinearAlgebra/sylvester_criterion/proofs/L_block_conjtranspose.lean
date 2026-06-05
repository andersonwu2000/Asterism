import Mathlib
import Problems.LinearAlgebra.sylvester_criterion.Defs

namespace Problems.LinearAlgebra.sylvester_criterion

-- block_conjtranspose: off-diagonal blocks of a Hermitian matrix are conjugate transposes
-- Uses IsHermitian of the reindexed submatrix; unfolds toBlocks defs and applies
-- the entry-wise conjugate-symmetry.
theorem block_conjtranspose {n : ℕ}
    (M : Matrix (Fin (n + 1)) (Fin (n + 1)) ℝ)
    (hHerm : M.IsHermitian) :
    (M.submatrix (finSumFinEquiv (m := n) (n := 1))
        (finSumFinEquiv (m := n) (n := 1))).toBlocks₂₁
      = (M.submatrix (finSumFinEquiv (m := n) (n := 1))
        (finSumFinEquiv (m := n) (n := 1))).toBlocks₁₂.conjTranspose := by
  have hSub : (M.submatrix (finSumFinEquiv (m := n) (n := 1))
      (finSumFinEquiv (m := n) (n := 1))).IsHermitian :=
    hHerm.submatrix _
  ext i j
  simp only [Matrix.toBlocks₂₁, Matrix.toBlocks₁₂, Matrix.conjTranspose, Matrix.transpose,
             Matrix.submatrix]
  exact congr_fun (congr_fun hSub (Sum.inl j)) (Sum.inr i)

end Problems.LinearAlgebra.sylvester_criterion
