import Library.LinearAlgebra.LeadingPrincipalMinor
import Library.LinearAlgebra.LeadingPrincipalMinorBlock
import Mathlib

open Library.LinearAlgebra.LeadingPrincipalMinor
open Library.LinearAlgebra.LeadingPrincipalMinorBlock

/-!
# Schur complement and positive semidefiniteness

This file proves that the `1 × 1` Schur complement of a real Hermitian matrix with all positive
leading principal minors is itself positive semidefinite, establishing the inductive step used in
Sylvester's criterion.  The key ingredients are a block-determinant factorization
(`schur_det_factor_2`) and the observation that a `Fin 1` matrix with positive determinant is
positive semidefinite (`possemidef_of_det_pos_fin_one`).
-/

namespace Library.LinearAlgebra.SchurComplementPosDef

/-- A `1 × 1` real matrix with positive determinant is positive semidefinite.
Every such matrix is diagonal, so the result follows from `Matrix.posSemidef_diagonal_iff`
applied to the unique entry. -/
theorem possemidef_of_det_pos_fin_one (S : Matrix (Fin 1) (Fin 1) ℝ)
    (h : 0 < S.det) : S.PosSemidef := by
  have hS0 : 0 < S 0 0 := Matrix.det_fin_one S ▸ h
  have hS_diag : S = Matrix.diagonal (fun _ => S 0 0) := by
    ext i j; fin_cases i; fin_cases j; simp [Matrix.diagonal]
  rw [hS_diag, Matrix.posSemidef_diagonal_iff]
  intro i; fin_cases i; exact le_of_lt hS0

/-- If every leading principal minor of `M` is positive, then `M.det > 0`.
This follows because `leadingPrincipalMinor M (Fin.last n)` is definitionally equal to `M.det`. -/
theorem mdet_pos_2 {n : ℕ}
    (M : Matrix (Fin (n + 1)) (Fin (n + 1)) ℝ)
    (hMinors : ∀ (k : Fin (n + 1)), 0 < leadingPrincipalMinor M k) :
    0 < M.det := by exact hMinors (Fin.last n)

/-- Block-determinant factorization: `M.det` equals the determinant of the top-left block times
the determinant of its Schur complement, provided the top-left block is positive definite.
The proof rewrites via `finSumFinEquiv`, expands with `det_fromBlocks₁₁`, and uses Hermitianity
to replace `toBlocks₂₁` with `toBlocks₁₂ᴴ`. -/
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
    Library.LinearAlgebra.LeadingPrincipalMinorBlock.block_conjtranspose M hHerm
  rw [← Matrix.det_submatrix_equiv_self (finSumFinEquiv (m := n) (n := 1)) M]
  conv_lhs => rw [← Matrix.fromBlocks_toBlocks (M.submatrix
    (finSumFinEquiv (m := n) (n := 1)) (finSumFinEquiv (m := n) (n := 1)))]
  rw [Matrix.det_fromBlocks₁₁, hconj, Matrix.invOf_eq_nonsing_inv]

/-- The `1 × 1` Schur complement has positive determinant when all leading principal minors of `M`
are positive and the top-left block is positive definite.  The block-determinant factorization
`schur_det_factor_2` gives `det M = det A · det S`; since both `det M` and `det A` are positive,
strict positivity of `det S` follows by scalar arithmetic. -/
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

/-- The `1 × 1` Schur complement `D - Bᴴ A⁻¹ B` of a real Hermitian matrix with positive leading
principal minors is positive semidefinite.  Positivity of its determinant follows from
`schur_det_pos`, and `possemidef_of_det_pos_fin_one` upgrades that scalar bound to
`PosSemidef` in the one-dimensional case. -/
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
