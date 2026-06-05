import Mathlib
import Problems.LinearAlgebra.sylvester_criterion.Defs
import Problems.LinearAlgebra.sylvester_criterion.proofs.L_possemidef_of_det_pos_fin_one
import Problems.LinearAlgebra.sylvester_criterion.proofs.L_schur_det_pos

namespace Problems.LinearAlgebra.sylvester_criterion

-- Schur complement (1×1) is PosSemidef via its determinant.
-- The 1-dim Schur complement S = D - Bᴴ A⁻¹ B has 0 < S.det (schur_det_pos:
-- det of the reindexed M factors as det A · det S, both numerator and det A > 0),
-- and for a Fin 1 matrix positive determinant gives PosSemidef
-- (possemidef_of_det_pos_fin_one). Each piece is strictly simpler: the det bound
-- is a scalar inequality, the Fin 1 upgrade is dimension-free.
theorem s11606 {n : ℕ}

    (M : Matrix (Fin (n + 1)) (Fin (n + 1)) ℝ)
    (hHerm : M.IsHermitian)
    (hMinors : ∀ (k : Fin (n + 1)), 0 < leadingPrincipalMinor M k)
    (hApd : (M.submatrix (finSumFinEquiv (m := n) (n := 1))
      (finSumFinEquiv (m := n) (n := 1))).toBlocks₁₁.PosDef) :
    ((M.submatrix (finSumFinEquiv (m := n) (n := 1))
        (finSumFinEquiv (m := n) (n := 1))).toBlocks₂₂
      - (M.submatrix (finSumFinEquiv (m := n) (n := 1))
          (finSumFinEquiv (m := n) (n := 1))).toBlocks₁₂.conjTranspose
        * (M.submatrix (finSumFinEquiv (m := n) (n := 1))
          (finSumFinEquiv (m := n) (n := 1))).toBlocks₁₁⁻¹
        * (M.submatrix (finSumFinEquiv (m := n) (n := 1))
          (finSumFinEquiv (m := n) (n := 1))).toBlocks₁₂).PosSemidef := by
  exact possemidef_of_det_pos_fin_one _ (schur_det_pos M hHerm hMinors hApd)


end Problems.LinearAlgebra.sylvester_criterion
