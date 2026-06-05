import Mathlib
import Problems.LinearAlgebra.sylvester_criterion.Defs
import Problems.LinearAlgebra.sylvester_criterion.proofs.L_block_conjtranspose_factor

namespace Problems.LinearAlgebra.sylvester_criterion

-- Schur block-determinant factorization: rewrite M.det as the det of the
-- finSumFinEquiv-reindexed matrix (det_submatrix_equiv_self), expand via
-- fromBlocks_toBlocks + det_fromBlocks₁₁ (Invertible toBlocks₁₁ from hApd),
-- then replace toBlocks₂₁ with toBlocks₁₂ᴴ via the sole sub-goal
-- block_conjtranspose_factor (needs hHerm); ⅟ → ⁻¹ closes the gap.
theorem s11612 {n : ℕ}
    (M : Matrix (Fin (n + 1)) (Fin (n + 1)) ℝ)
    (hHerm : M.IsHermitian)
    (hApd : (M.submatrix (finSumFinEquiv (m := n) (n := 1))
      (finSumFinEquiv (m := n) (n := 1))).toBlocks₁₁.PosDef) :
    M.det = (M.submatrix (finSumFinEquiv (m := n) (n := 1))
        (finSumFinEquiv (m := n) (n := 1))).toBlocks₁₁.det
      * ((M.submatrix (finSumFinEquiv (m := n) (n := 1))
          (finSumFinEquiv (m := n) (n := 1))).toBlocks₂₂
        - (M.submatrix (finSumFinEquiv (m := n) (n := 1))
          (finSumFinEquiv (m := n) (n := 1))).toBlocks₁₂.conjTranspose
          * (M.submatrix (finSumFinEquiv (m := n) (n := 1))
            (finSumFinEquiv (m := n) (n := 1))).toBlocks₁₁⁻¹
          * (M.submatrix (finSumFinEquiv (m := n) (n := 1))
            (finSumFinEquiv (m := n) (n := 1))).toBlocks₁₂).det  := by
  have hInv : Invertible (M.submatrix (finSumFinEquiv (m := n) (n := 1))
      (finSumFinEquiv (m := n) (n := 1))).toBlocks₁₁ := hApd.isUnit.invertible
  have hconj : (M.submatrix (finSumFinEquiv (m := n) (n := 1))
      (finSumFinEquiv (m := n) (n := 1))).toBlocks₂₁
      = (M.submatrix (finSumFinEquiv (m := n) (n := 1))
        (finSumFinEquiv (m := n) (n := 1))).toBlocks₁₂.conjTranspose :=
    block_conjtranspose_factor M hHerm
  rw [← Matrix.det_submatrix_equiv_self (finSumFinEquiv (m := n) (n := 1)) M]
  conv_lhs => rw [← Matrix.fromBlocks_toBlocks (M.submatrix
    (finSumFinEquiv (m := n) (n := 1)) (finSumFinEquiv (m := n) (n := 1)))]
  rw [Matrix.det_fromBlocks₁₁, hconj, Matrix.invOf_eq_nonsing_inv]

end Problems.LinearAlgebra.sylvester_criterion
