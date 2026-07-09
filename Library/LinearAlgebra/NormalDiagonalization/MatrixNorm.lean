import Mathlib

/-!
# Normal diagonalization: matrix norm lemmas

This file establishes that an upper-triangular normal matrix over `ℂ` is diagonal.
The argument proceeds in three steps: collapse each column's squared-norm sum to its
diagonal entry (using triangularity and an inductive hypothesis on earlier rows), apply
an abstract fact that a nonneg sum equalling one of its terms forces all others to zero,
and extract the column-vs-row norm identity from the normality condition `Commute Mᴴ M`.
-/

namespace Library.LinearAlgebra.NormalDiagonalization.MatrixNorm

variable {n : ℕ}

/-- If the sum of squared norms `∑ ‖f k‖²` equals its `i`-th term `‖f i‖²`, then every
other term `f k` (with `k ≠ i`) is zero. -/
theorem sum_norm_sq_eq_single_imp_zero (f : Fin n → ℂ) (i : Fin n)
    (h : ∑ k, ‖f k‖ ^ 2 = ‖f i‖ ^ 2) :
    ∀ k, k ≠ i → f k = 0 := by
  intro k hk
  have hnn : ∀ j : Fin n, 0 ≤ ‖f j‖ ^ 2 := fun j => sq_nonneg _
  have hge : 0 ≤ ∑ j ∈ Finset.univ.erase i, ‖f j‖ ^ 2 :=
    Finset.sum_nonneg (fun j _ => hnn j)
  have hsplit : (∑ j ∈ Finset.univ.erase i, ‖f j‖ ^ 2) + ‖f i‖ ^ 2 =
      ∑ j : Fin n, ‖f j‖ ^ 2 :=
    Finset.sum_erase_add Finset.univ (fun j => ‖f j‖ ^ 2) (Finset.mem_univ i)
  have key : ∑ j ∈ Finset.univ.erase i, ‖f j‖ ^ 2 = 0 := by
    linarith [hsplit.trans h]
  have hk2 : ‖f k‖ ^ 2 = 0 :=
    le_antisymm
      (key ▸ Finset.single_le_sum (fun j _ => hnn j)
        (Finset.mem_erase.mpr ⟨hk, Finset.mem_univ k⟩))
      (hnn k)
  exact norm_eq_zero.mp (by nlinarith [norm_nonneg (f k)])

/-- For an upper-triangular matrix `M` (with `htri : M.BlockTriangular id`) whose rows
`j < i` are already diagonal (`ih`), the squared-norm sum `∑ k, ‖M k i‖²` collapses to
`‖M i i‖²`: triangularity kills entries above row `i` and the inductive hypothesis kills
entries below row `i` in column `i`. -/
theorem col_sum_collapse (M : Matrix (Fin n) (Fin n) ℂ)
    (htri : M.BlockTriangular id) (i : Fin n)
    (ih : ∀ j : Fin n, j < i → ∀ k : Fin n, j ≠ k → M j k = 0) :
    ∑ k, ‖M k i‖ ^ 2 = ‖M i i‖ ^ 2 := by
  apply Finset.sum_eq_single i
  · intro k _ hki
    rcases lt_or_gt_of_ne hki with hlt | hgt
    · have h0 : M k i = 0 := ih k hlt i hki
      simp [h0]
    · have h0 : M k i = 0 := htri hgt
      simp [h0]
  · intro hi
    exact absurd (Finset.mem_univ i) hi

/-- For a normal matrix `M` (given as `Commute Mᴴ M`), the column and row squared-norm sums
agree: `∑ k, ‖M k i‖² = ∑ k, ‖M i k‖²`. This follows by equating the `(i, i)` diagonal
entries of `MᴴM` and `MMᴴ`. -/
theorem row_col_norm_eq (M : Matrix (Fin n) (Fin n) ℂ)
    (hcomm : Commute (Matrix.conjTranspose M) M) (i : Fin n) :
    ∑ k, ‖M k i‖ ^ 2 = ∑ k, ‖M i k‖ ^ 2 := by
  have hdiag : (Matrix.conjTranspose M * M) i i = (M * Matrix.conjTranspose M) i i :=
    congr_fun (congr_fun hcomm i) i
  have star_mul_re : ∀ z : ℂ, (star z * z).re = ‖z‖ ^ 2 := fun z => by
    have h : star z * z = ↑(Complex.normSq z) := by
      rw [Complex.star_def]
      exact Complex.normSq_eq_conj_mul_self.symm
    rw [h, Complex.ofReal_re, Complex.normSq_eq_norm_sq]
  have mul_star_re : ∀ z : ℂ, (z * star z).re = ‖z‖ ^ 2 := fun z => by
    rw [mul_comm]; exact star_mul_re z
  have lhs_eq : ∑ k, ‖M k i‖ ^ 2 = ((Matrix.conjTranspose M * M) i i).re := by
    simp only [Matrix.mul_apply, Matrix.conjTranspose_apply, Complex.re_sum]
    congr 1; ext k
    exact (star_mul_re (M k i)).symm
  have rhs_eq : ∑ k, ‖M i k‖ ^ 2 = ((M * Matrix.conjTranspose M) i i).re := by
    simp only [Matrix.mul_apply, Matrix.conjTranspose_apply, Complex.re_sum]
    congr 1; ext k
    exact (mul_star_re (M i k)).symm
  rw [lhs_eq, rhs_eq, hdiag]

/-- An upper-triangular matrix `M` satisfying the column-vs-row squared-norm identity
`∑ ‖M k i‖² = ∑ ‖M i k‖²` for every `i` is diagonal. The proof is by strong induction on
the row index: the inductive hypothesis and triangularity collapse each column sum to the
diagonal entry, and `sum_norm_sq_eq_single_imp_zero` then forces all off-diagonal row
entries to zero. -/
theorem triangular_rowcol_eq_imp_diag (M : Matrix (Fin n) (Fin n) ℂ)
    (htri : M.BlockTriangular id)
    (hsum : ∀ i, ∑ k, ‖M k i‖ ^ 2 = ∑ k, ‖M i k‖ ^ 2) :
    M.IsDiag  := by
  have aux : ∀ m : ℕ, ∀ i : Fin n, i.val = m → ∀ k : Fin n, i ≠ k → M i k = 0 := by
    intro m
    induction m using Nat.strong_induction_on with
    | _ m ih =>
      intro i hi k hik
      have ihrows : ∀ j : Fin n, j < i → ∀ k' : Fin n, j ≠ k' → M j k' = 0 :=
        fun j hj k' hjk' => ih j.val ((Fin.lt_def.mp hj).trans_eq hi) j rfl k' hjk'
      have hcol : ∑ k, ‖M k i‖ ^ 2 = ‖M i i‖ ^ 2 := col_sum_collapse M htri i ihrows
      have hrow : ∑ k, ‖M i k‖ ^ 2 = ‖M i i‖ ^ 2 := by rw [← hsum i]; exact hcol
      exact sum_norm_sq_eq_single_imp_zero (fun k => M i k) i hrow k (Ne.symm hik)
  intro i j hij
  exact aux i.val i rfl j hij

/-- An upper-triangular normal matrix over `ℂ` is diagonal. Normality (`Commute Mᴴ M`)
provides the column-vs-row squared-norm identity via `row_col_norm_eq`, and
`triangular_rowcol_eq_imp_diag` then completes the argument by strong induction. -/
theorem matrix_core (M : Matrix (Fin n) (Fin n) ℂ)
    (htri : M.BlockTriangular id) (hcomm : Commute (Matrix.conjTranspose M) M) :
    M.IsDiag := by
  have h_rc : ∀ i, ∑ k, ‖M k i‖ ^ 2 = ∑ k, ‖M i k‖ ^ 2 := row_col_norm_eq M hcomm
  exact triangular_rowcol_eq_imp_diag M htri h_rc

end Library.LinearAlgebra.NormalDiagonalization.MatrixNorm
