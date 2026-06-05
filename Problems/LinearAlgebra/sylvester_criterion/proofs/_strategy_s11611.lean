import Mathlib
import Problems.LinearAlgebra.sylvester_criterion.Defs
import Problems.LinearAlgebra.sylvester_criterion.proofs.L_mdet_pos_2
import Problems.LinearAlgebra.sylvester_criterion.proofs.L_schur_det_factor_2

namespace Problems.LinearAlgebra.sylvester_criterion

-- Schur complement (1×1) has positive determinant via the block-determinant factorization.
-- det M = det(toBlocks₁₁) · det(Schur) (schur_det_factor_2, using hHerm to rewrite toBlocks₂₁ =
-- toBlocks₁₂ᴴ); det M > 0 (mdet_pos_2, the last leading minor) and det(toBlocks₁₁) > 0 (hApd.det_pos)
-- force det(Schur) > 0. Each piece is strictly simpler: a scalar positivity (mdet_pos_2) and a
-- determinant identity (schur_det_factor_2); the final step is one scalar division (nlinarith).
theorem s11611 {n : ℕ}
    (M : Matrix (Fin (n + 1)) (Fin (n + 1)) ℝ)
    (hHerm : M.IsHermitian)
    (hMinors : ∀ (k : Fin (n + 1)), 0 < leadingPrincipalMinor M k)
    (hApd : (M.submatrix (finSumFinEquiv (m := n) (n := 1))
      (finSumFinEquiv (m := n) (n := 1))).toBlocks₁₁.PosDef) :
    0 < ((M.submatrix (finSumFinEquiv (m := n) (n := 1))
        (finSumFinEquiv (m := n) (n := 1))).toBlocks₂₂
      - (M.submatrix (finSumFinEquiv (m := n) (n := 1))
          (finSumFinEquiv (m := n) (n := 1))).toBlocks₁₂.conjTranspose
        * (M.submatrix (finSumFinEquiv (m := n) (n := 1))
          (finSumFinEquiv (m := n) (n := 1))).toBlocks₁₁⁻¹
        * (M.submatrix (finSumFinEquiv (m := n) (n := 1))
          (finSumFinEquiv (m := n) (n := 1))).toBlocks₁₂).det  := by
  have hMpos : 0 < M.det := mdet_pos_2 M hMinors
  have hdetA : 0 < (M.submatrix (finSumFinEquiv (m := n) (n := 1))
      (finSumFinEquiv (m := n) (n := 1))).toBlocks₁₁.det := hApd.det_pos
  have hfactor : M.det = (M.submatrix (finSumFinEquiv (m := n) (n := 1))
      (finSumFinEquiv (m := n) (n := 1))).toBlocks₁₁.det
      * ((M.submatrix (finSumFinEquiv (m := n) (n := 1))
          (finSumFinEquiv (m := n) (n := 1))).toBlocks₂₂
        - (M.submatrix (finSumFinEquiv (m := n) (n := 1))
          (finSumFinEquiv (m := n) (n := 1))).toBlocks₁₂.conjTranspose
          * (M.submatrix (finSumFinEquiv (m := n) (n := 1))
            (finSumFinEquiv (m := n) (n := 1))).toBlocks₁₁⁻¹
          * (M.submatrix (finSumFinEquiv (m := n) (n := 1))
            (finSumFinEquiv (m := n) (n := 1))).toBlocks₁₂).det :=
    schur_det_factor_2 M hHerm hApd
  rw [hfactor] at hMpos
  nlinarith [hdetA, hMpos]

end Problems.LinearAlgebra.sylvester_criterion
