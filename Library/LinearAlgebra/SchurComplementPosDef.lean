import Library.LinearAlgebra.LeadingPrincipalMinor
import Library.LinearAlgebra.LeadingPrincipalMinorBlock
import Mathlib

open Library.LinearAlgebra.LeadingPrincipalMinor
open Library.LinearAlgebra.LeadingPrincipalMinorBlock

namespace Library.LinearAlgebra.SchurComplementPosDef

-- possemidef_of_det_pos_fin_one: 1×1 real matrix with positive det is PosSemidef
-- via diagonal rewrite: every 1×1 matrix is diagonal, then use posSemidef_diagonal_iff
theorem possemidef_of_det_pos_fin_one (S : Matrix (Fin 1) (Fin 1) ℝ)
    (h : 0 < S.det) : S.PosSemidef := by
  have hS0 : 0 < S 0 0 := Matrix.det_fin_one S ▸ h
  have hS_diag : S = Matrix.diagonal (fun _ => S 0 0) := by
    ext i j; fin_cases i; fin_cases j; simp [Matrix.diagonal]
  rw [hS_diag, Matrix.posSemidef_diagonal_iff]
  intro i; fin_cases i; exact le_of_lt hS0

-- mdet_pos_2: det M > 0 follows because leadingPrincipalMinor M (Fin.last n) is
-- definitionally equal to M.det (castLE at Fin.last n is the identity on Fin (n+1)).
theorem mdet_pos_2 {n : ℕ}
    (M : Matrix (Fin (n + 1)) (Fin (n + 1)) ℝ)
    (hMinors : ∀ (k : Fin (n + 1)), 0 < leadingPrincipalMinor M k) :
    0 < M.det := by exact hMinors (Fin.last n)

-- Schur block-determinant factorization: rewrite M.det as the det of the
-- finSumFinEquiv-reindexed matrix (det_submatrix_equiv_self), expand via
-- fromBlocks_toBlocks + det_fromBlocks₁₁ (Invertible toBlocks₁₁ from hApd),
-- then replace toBlocks₂₁ with toBlocks₁₂ᴴ via the sole sub-goal
-- block_conjtranspose_factor (needs hHerm); ⅟ → ⁻¹ closes the gap.
theorem schur_det_factor_2 {n : ℕ}
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

-- Schur complement (1×1) has positive determinant via the block-determinant factorization.
-- det M = det(toBlocks₁₁) · det(Schur) (schur_det_factor_2, using hHerm to rewrite toBlocks₂₁ =
-- toBlocks₁₂ᴴ); det M > 0 (mdet_pos_2, the last leading minor) and det(toBlocks₁₁) > 0 (hApd.det_pos)
-- force det(Schur) > 0. Each piece is strictly simpler: a scalar positivity (mdet_pos_2) and a
-- determinant identity (schur_det_factor_2); the final step is one scalar division (nlinarith).
theorem schur_det_pos {n : ℕ}
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

-- Schur complement (1×1) is PosSemidef via its determinant.
-- The 1-dim Schur complement S = D - Bᴴ A⁻¹ B has 0 < S.det (schur_det_pos:
-- det of the reindexed M factors as det A · det S, both numerator and det A > 0),
-- and for a Fin 1 matrix positive determinant gives PosSemidef
-- (possemidef_of_det_pos_fin_one). Each piece is strictly simpler: the det bound
-- is a scalar inequality, the Fin 1 upgrade is dimension-free.
theorem schur_complement_possemidef {n : ℕ}

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

end Library.LinearAlgebra.SchurComplementPosDef
