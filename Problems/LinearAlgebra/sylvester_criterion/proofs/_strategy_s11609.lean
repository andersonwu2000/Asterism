import Mathlib
import Problems.LinearAlgebra.sylvester_criterion.Defs
import Problems.LinearAlgebra.sylvester_criterion.proofs.L_mdet_pos
import Problems.LinearAlgebra.sylvester_criterion.proofs.L_schur_det_factor

namespace Problems.LinearAlgebra.sylvester_criterion

-- 0 < S.det for the 1×1 Schur complement S, via det factorization.
-- det M = det(toBlocks₁₁) · det S (schur_det_factor, det_fromBlocks₁₁ over the
-- reindexed M); det M > 0 (mdet_pos, from the top leading minor) and
-- det(toBlocks₁₁) > 0 (hApd.det_pos) force 0 < det S by mul_pos cancellation.

theorem s11609 {n : ℕ}
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
  have hAdet : 0 < (M.submatrix (finSumFinEquiv (m := n) (n := 1))
      (finSumFinEquiv (m := n) (n := 1))).toBlocks₁₁.det := hApd.det_pos
  have hMdet : 0 < M.det := mdet_pos M hMinors
  have hfactor : M.det = (M.submatrix (finSumFinEquiv (m := n) (n := 1))
      (finSumFinEquiv (m := n) (n := 1))).toBlocks₁₁.det
      * ((M.submatrix (finSumFinEquiv (m := n) (n := 1))
        (finSumFinEquiv (m := n) (n := 1))).toBlocks₂₂
      - (M.submatrix (finSumFinEquiv (m := n) (n := 1))
          (finSumFinEquiv (m := n) (n := 1))).toBlocks₁₂.conjTranspose
        * (M.submatrix (finSumFinEquiv (m := n) (n := 1))
          (finSumFinEquiv (m := n) (n := 1))).toBlocks₁₁⁻¹
        * (M.submatrix (finSumFinEquiv (m := n) (n := 1))
          (finSumFinEquiv (m := n) (n := 1))).toBlocks₁₂).det := schur_det_factor M hApd
  rw [hfactor] at hMdet
  exact (mul_pos_iff_of_pos_left hAdet).mp hMdet


end Problems.LinearAlgebra.sylvester_criterion
