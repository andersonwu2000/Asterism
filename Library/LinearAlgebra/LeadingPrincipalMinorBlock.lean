import Library.LinearAlgebra.LeadingPrincipalMinor
import Mathlib

open Library.LinearAlgebra.LeadingPrincipalMinor

namespace Library.LinearAlgebra.LeadingPrincipalMinorBlock

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

theorem block_conjtranspose_factor {n : ℕ}
    (M : Matrix (Fin (n + 1)) (Fin (n + 1)) ℝ)
    (hHerm : M.IsHermitian) :
    (M.submatrix (finSumFinEquiv (m := n) (n := 1))
        (finSumFinEquiv (m := n) (n := 1))).toBlocks₂₁
      = (M.submatrix (finSumFinEquiv (m := n) (n := 1))
        (finSumFinEquiv (m := n) (n := 1))).toBlocks₁₂.conjTranspose := by apply block_conjtranspose <;> assumption

-- block_hermitian: IsHermitian is preserved by submatrix; toBlocks₁₁ is Sum.inl submatrix
theorem block_hermitian {n : ℕ} (M : Matrix (Fin (n + 1)) (Fin (n + 1)) ℝ)
    (hHerm : M.IsHermitian) :
    (M.submatrix (finSumFinEquiv (m := n) (n := 1))
      (finSumFinEquiv (m := n) (n := 1))).toBlocks₁₁.IsHermitian := by
  simp only [Matrix.toBlocks₁₁]
  exact hHerm.submatrix (↑finSumFinEquiv ∘ Sum.inl)

-- Each leading block-minor equals a leading minor of M, hence positive.
-- The top-left n×n block B = M.submatrix (castAdd 1) (castAdd 1); its leading
-- (k+1)-minor reindexes to M's leading minor at k.castSucc (val-preserving Fin
-- maps coincide), so `congr 1` after unfolding closes the equality; positivity
-- then follows from hMinors at k.castSucc. No sub-goals needed.
theorem block_minors_pos {n : ℕ} (M : Matrix (Fin (n + 1)) (Fin (n + 1)) ℝ)
    (hMinors : ∀ (k : Fin (n + 1)), 0 < leadingPrincipalMinor M k) :
    ∀ (k : Fin n), 0 < leadingPrincipalMinor
      (M.submatrix (finSumFinEquiv (m := n) (n := 1))
        (finSumFinEquiv (m := n) (n := 1))).toBlocks₁₁ k  := by
  intro k
  have h_minor_eq : leadingPrincipalMinor
      (M.submatrix (finSumFinEquiv (m := n) (n := 1))
        (finSumFinEquiv (m := n) (n := 1))).toBlocks₁₁ k
      = leadingPrincipalMinor M k.castSucc := by
    simp only [leadingPrincipalMinor, Matrix.toBlocks₁₁]
    congr 1
  rw [h_minor_eq]
  exact hMinors k.castSucc

end Library.LinearAlgebra.LeadingPrincipalMinorBlock
