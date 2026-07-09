import Library.LinearAlgebra.LeadingPrincipalMinor
import Library.LinearAlgebra.LeadingPrincipalMinorBlock
import Library.LinearAlgebra.SchurComplementPosDef
import Mathlib

/-!
# Sylvester's Criterion

This file proves Sylvester's criterion: a real symmetric matrix is positive definite if and only if
all of its leading principal minors are strictly positive. The reverse direction proceeds by
induction on dimension using a Schur-complement argument, and the forward direction follows from the
fact that each leading block of a positive definite matrix is itself positive definite.
-/

open Library.LinearAlgebra.LeadingPrincipalMinor
open Library.LinearAlgebra.LeadingPrincipalMinorBlock
open Library.LinearAlgebra.SchurComplementPosDef

namespace Library.LinearAlgebra.SylvesterCriterion

/-- A positive semidefinite matrix with nonzero determinant is positive definite.
All eigenvalues are nonneg by semidefiniteness, and a zero eigenvalue would force the product of
eigenvalues (i.e., the determinant) to vanish, contradicting `hd`. -/
theorem posdef_of_possemidef_det_ne_zero {n : Type*} [Fintype n] [DecidableEq n]
    {M : Matrix n n ℝ} (hM : M.PosSemidef) (hd : M.det ≠ 0) : M.PosDef := by
  rw [hM.isHermitian.posDef_iff_eigenvalues_pos]
  intro i
  refine lt_of_le_of_ne (hM.eigenvalues_nonneg i) (Ne.symm ?_)
  intro h0
  apply hd
  rw [hM.isHermitian.det_eq_prod_eigenvalues]
  exact Finset.prod_eq_zero (Finset.mem_univ i) (by simp [← h0])

/-- Every `0 × 0` real matrix is positive definite, since there are no nonzero vectors to test. -/
theorem posdef_empty (M : Matrix (Fin 0) (Fin 0) ℝ) (hHerm : M.IsHermitian) :
    M.PosDef := by
  refine ⟨hHerm, fun x hx => ?_⟩
  exact absurd (Finsupp.ext (fun (i : Fin 0) => Fin.elim0 i)) hx

/-- The last leading principal minor of an `(n+1) × (n+1)` matrix equals its full determinant, so
positivity of all leading minors implies the determinant is nonzero. -/
theorem posdef_succ_det_ne_zero {n : ℕ}
    (M : Matrix (Fin (n + 1)) (Fin (n + 1)) ℝ)
    (hMinors : ∀ (k : Fin (n + 1)), 0 < leadingPrincipalMinor M k) :
    M.det ≠ 0 := by
  have hlast := hMinors (Fin.last n)
  have heq : leadingPrincipalMinor M (Fin.last n) = M.det := by
    simp [leadingPrincipalMinor, Fin.last]
  linarith [heq ▸ hlast]

/-- Given the inductive hypothesis `ih` for `n × n` matrices, the leading `n × n` block of an
`(n+1) × (n+1)` Hermitian matrix with positive leading minors is positive definite. -/
theorem leading_block_posdef {n : ℕ}
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

/-- An `(n+1) × (n+1)` Hermitian matrix with all leading minors positive is positive semidefinite.
The proof reindexes via `finSumFinEquiv`, uses `leading_block_posdef` for a positive definite
top-left block, and then applies `Matrix.PosDef.fromBlocks₁₁` with the Schur complement. -/
theorem posdef_succ_possemidef {n : ℕ}
    (ih : ∀ (M : Matrix (Fin n) (Fin n) ℝ), M.IsHermitian →
      (∀ (k : Fin n), 0 < leadingPrincipalMinor M k) → M.PosDef)
    (M : Matrix (Fin (n + 1)) (Fin (n + 1)) ℝ)
    (hHerm : M.IsHermitian)
    (hMinors : ∀ (k : Fin (n + 1)), 0 < leadingPrincipalMinor M k) :
    M.PosSemidef  := by
  classical
  rw [← Matrix.posSemidef_submatrix_equiv (finSumFinEquiv (m := n) (n := 1))]
  have hApd : (M.submatrix (finSumFinEquiv (m := n) (n := 1))
      (finSumFinEquiv (m := n) (n := 1))).toBlocks₁₁.PosDef :=
    leading_block_posdef ih M hHerm hMinors
  letI : Invertible (M.submatrix (finSumFinEquiv (m := n) (n := 1))
      (finSumFinEquiv (m := n) (n := 1))).toBlocks₁₁ := hApd.isUnit.invertible
  have hC := block_conjtranspose M hHerm
  rw [← Matrix.fromBlocks_toBlocks (M.submatrix (finSumFinEquiv (m := n) (n := 1))
        (finSumFinEquiv (m := n) (n := 1))), hC,
      Matrix.PosDef.fromBlocks₁₁ _ _ hApd]
  exact schur_complement_possemidef M hHerm hMinors hApd

/-- Inductive step of Sylvester's criterion: an `(n+1) × (n+1)` Hermitian matrix with all leading
minors positive is positive definite, combining `posdef_succ_possemidef` (which gives `PosSemidef`)
with `posdef_succ_det_ne_zero` (which gives `det ≠ 0`) via `posdef_of_possemidef_det_ne_zero`. -/
theorem posdef_succ_step {n : ℕ}
    (ih : ∀ (M : Matrix (Fin n) (Fin n) ℝ), M.IsHermitian →
      (∀ (k : Fin n), 0 < leadingPrincipalMinor M k) → M.PosDef)
    (M : Matrix (Fin (n + 1)) (Fin (n + 1)) ℝ)
    (hHerm : M.IsHermitian)
    (hMinors : ∀ (k : Fin (n + 1)), 0 < leadingPrincipalMinor M k) :
    M.PosDef  := by
  have hPSD : M.PosSemidef := posdef_succ_possemidef ih M hHerm hMinors
  have hdet : M.det ≠ 0 := posdef_succ_det_ne_zero M hMinors
  exact Library.LinearAlgebra.SylvesterCriterion.posdef_of_possemidef_det_ne_zero hPSD hdet

/-- Each leading principal minor of a positive definite matrix is strictly positive.
The `k`-th leading block is a submatrix via the injective map `Fin.castLE`, so `PosDef.submatrix`
applies, and `PosDef.det_pos` gives the positive determinant equal to the leading minor. -/
theorem minors_pos_of_posdef {n : ℕ} (M : Matrix (Fin n) (Fin n) ℝ) :
    M.PosDef → ∀ k : Fin n, 0 < leadingPrincipalMinor M k := by
  intro hM k
  unfold leadingPrincipalMinor
  simp only
  have hk : k.val + 1 ≤ n := by have := k.isLt; omega
  have hinj : Function.Injective (Fin.castLE hk) := Fin.castLE_injective hk
  exact (hM.submatrix hinj).det_pos

/-- Reverse direction of Sylvester's criterion: if all leading principal minors of a Hermitian
matrix are positive then the matrix is positive definite. The proof proceeds by induction on `n`,
with `posdef_empty` as the base case and `posdef_succ_step` as the inductive step. -/
theorem posdef_of_minors_pos {n : ℕ} (M : Matrix (Fin n) (Fin n) ℝ) :
    M.IsHermitian → (∀ k : Fin n, 0 < leadingPrincipalMinor M k) → M.PosDef  := by
  revert M
  induction n with
  | zero =>
    intro M hHerm _
    exact posdef_empty M hHerm
  | succ n ih =>
    intro M hHerm hMinors
    exact posdef_succ_step ih M hHerm hMinors

/-- **Sylvester's criterion**: a real Hermitian matrix is positive definite if and only if all of
its leading principal minors are strictly positive. -/
theorem main : ∀ {n : ℕ} (M : Matrix (Fin n) (Fin n) ℝ),
    M.IsHermitian →
    (M.PosDef ↔ ∀ k : Fin n, 0 < leadingPrincipalMinor M k)  := by
  intro n M hHerm
  exact Iff.intro (minors_pos_of_posdef M) (posdef_of_minors_pos M hHerm)

end Library.LinearAlgebra.SylvesterCriterion
