import Library.LinearAlgebra.LeadingPrincipalMinor
import Library.LinearAlgebra.LeadingPrincipalMinorBlock
import Library.LinearAlgebra.SchurComplementPosDef
import Mathlib

open Library.LinearAlgebra.LeadingPrincipalMinor
open Library.LinearAlgebra.LeadingPrincipalMinorBlock
open Library.LinearAlgebra.SchurComplementPosDef

namespace Library.LinearAlgebra.SylvesterCriterion

-- A PosSemidef matrix with nonzero determinant is PosDef, via the eigenvalue criterion.
-- PosDef ↔ all eigenvalues > 0; each eigenvalue is ≥ 0 (PosSemidef), and none is 0 since
-- det = ∏ eigenvalues ≠ 0 (a zero eigenvalue would force the product to vanish).
theorem posdef_of_possemidef_det_ne_zero {n : Type*} [Fintype n] [DecidableEq n]
    {M : Matrix n n ℝ} (hM : M.PosSemidef) (hd : M.det ≠ 0) : M.PosDef := by
  rw [hM.isHermitian.posDef_iff_eigenvalues_pos]
  intro i
  refine lt_of_le_of_ne (hM.eigenvalues_nonneg i) (Ne.symm ?_)
  intro h0
  apply hd
  rw [hM.isHermitian.det_eq_prod_eigenvalues]
  exact Finset.prod_eq_zero (Finset.mem_univ i) (by simp [← h0])

theorem posdef_of_possemidef_det_ne_zero_2 {n : Type*} [Fintype n] [DecidableEq n]
    {M : Matrix n n ℝ} (hM : M.PosSemidef) (hd : M.det ≠ 0) : M.PosDef := by apply posdef_of_possemidef_det_ne_zero <;> assumption

-- posdef_empty: 0×0 matrix is vacuously PosDef (no non-zero vectors in Fin 0 → ℝ)
theorem posdef_empty (M : Matrix (Fin 0) (Fin 0) ℝ) (hHerm : M.IsHermitian) :
    M.PosDef := by
  refine ⟨hHerm, fun x hx => ?_⟩
  exact absurd (Finsupp.ext (fun (i : Fin 0) => Fin.elim0 i)) hx

-- posdef_succ_det_ne_zero: last leading principal minor equals M.det, so positivity implies det ≠ 0
theorem posdef_succ_det_ne_zero {n : ℕ}
    (M : Matrix (Fin (n + 1)) (Fin (n + 1)) ℝ)
    (hMinors : ∀ (k : Fin (n + 1)), 0 < leadingPrincipalMinor M k) :
    M.det ≠ 0 := by
  have hlast := hMinors (Fin.last n)
  have heq : leadingPrincipalMinor M (Fin.last n) = M.det := by
    simp [leadingPrincipalMinor, Fin.last]
  linarith [heq ▸ hlast]

-- Apply `ih` to the leading n×n block A = (reindexed M).toBlocks₁₁.
-- ih needs (1) A Hermitian and (2) all leading principal minors of A positive.
--   • block_hermitian   — A is Hermitian (submatrix of a Hermitian matrix);
--   • block_minors_pos  — each leading minor of A equals a leading minor of M (> 0).
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

-- Schur-complement induction step: M (size n+1) is PosSemidef. Reindex via
-- `finSumFinEquiv` into 2×2 blocks, then `PosDef.fromBlocks₁₁` reduces PosSemidef
-- of the whole to PosSemidef of the Schur complement. Three strictly-simpler pieces:
--   • leading_block_posdef     — the top-left n×n block is PosDef (uses `ih`);
--   • block_conjtranspose      — Hermitian symmetry of the off-diagonal blocks;
--   • schur_complement_possemidef — the 1-dim Schur complement is PosSemidef.
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

-- Schur-complement upgrade, factored into: M PosSemidef, M.det ≠ 0, and the
-- generic upgrade lemma (PosSemidef + det ≠ 0 ⇒ PosDef). The upgrade is
-- re-declared as our own sub-goal (a proven sibling exists but lives in another
-- strategy module and is not auto-imported; Tier-1 dedup aliases this to it).
-- PosSemidef carries the (n×n block PosDef ⇒ Schur ≥ 0) argument; det ≠ 0 is the
-- top leading minor being positive. Both strictly weaker than the parent PosDef goal.
theorem posdef_succ_step {n : ℕ}
    (ih : ∀ (M : Matrix (Fin n) (Fin n) ℝ), M.IsHermitian →
      (∀ (k : Fin n), 0 < leadingPrincipalMinor M k) → M.PosDef)
    (M : Matrix (Fin (n + 1)) (Fin (n + 1)) ℝ)
    (hHerm : M.IsHermitian)
    (hMinors : ∀ (k : Fin (n + 1)), 0 < leadingPrincipalMinor M k) :
    M.PosDef  := by
  have hPSD : M.PosSemidef := posdef_succ_possemidef ih M hHerm hMinors
  have hdet : M.det ≠ 0 := posdef_succ_det_ne_zero M hMinors
  exact posdef_of_possemidef_det_ne_zero_2 hPSD hdet

-- minors_pos_of_posdef: PosDef.submatrix + PosDef.det_pos closes each leading minor directly.
-- Each leading k-block is a submatrix via Fin.castLE (injective), so PosDef.submatrix applies;
-- PosDef.det_pos then gives the positive determinant = leadingPrincipalMinor.
theorem minors_pos_of_posdef {n : ℕ} (M : Matrix (Fin n) (Fin n) ℝ) :
    M.PosDef → ∀ k : Fin n, 0 < leadingPrincipalMinor M k := by
  intro hM k
  unfold leadingPrincipalMinor
  simp only
  have hk : k.val + 1 ≤ n := by have := k.isLt; omega
  have hinj : Function.Injective (Fin.castLE hk) := Fin.castLE_injective hk
  exact (hM.submatrix hinj).det_pos

-- Sylvester reverse direction: induction on the dimension n (revert M first so the
-- inductive hypothesis quantifies over every n×n matrix).
--  • base `posdef_empty`: the 0×0 matrix is PosDef vacuously.
--  • step `posdef_succ_step`: given ih (the criterion for n) plus the (n+1) leading
--    minors, the Schur-complement argument upgrades to PosDef.
-- `induction` is the combinator; each branch is strictly simpler (base trivial; step
-- has ih in hand, so it no longer carries the induction setup).
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

-- Sylvester's criterion: split the iff into its two implications.
-- Forward (`minors_pos_of_posdef`): each leading block is a PosDef submatrix, so its
-- determinant (= the leading minor) is positive — short, no induction.
-- Reverse (`posdef_of_minors_pos`): induction on n via Schur complement, upgrading
-- PosSemidef to PosDef using the proved sibling. Iff.intro recombines them.
theorem main : ∀ {n : ℕ} (M : Matrix (Fin n) (Fin n) ℝ),
    M.IsHermitian →
    (M.PosDef ↔ ∀ k : Fin n, 0 < leadingPrincipalMinor M k)  := by
  intro n M hHerm
  exact Iff.intro (minors_pos_of_posdef M) (posdef_of_minors_pos M hHerm)

end Library.LinearAlgebra.SylvesterCriterion
