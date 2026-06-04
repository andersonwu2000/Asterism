import Mathlib

namespace Library.LinearAlgebra.NormalDiagonalization.MatrixNorm

-- entry_kind: Builder
-- sum_norm_sq_eq_single_imp_zero: if a sum of squared norms equals its i-th term,
-- all other terms vanish (nonneg sum collapsed to one summand via erase decomposition)
theorem sum_norm_sq_eq_single_imp_zero {n : ℕ} (f : Fin n → ℂ) (i : Fin n)
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

-- col_sum_collapse: column i's squared-norm sum collapses to ‖M i i‖²
-- because htri kills entries above row i and ih kills entries below row i in column i.
theorem col_sum_collapse {n : ℕ} (M : Matrix (Fin n) (Fin n) ℂ)
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

-- entry_kind: Builder
-- row_col_norm_eq: diagonal of Mᴴ*M and M*Mᴴ agree by normality, giving equal column/row 2-norms
theorem row_col_norm_eq {n : ℕ} (M : Matrix (Fin n) (Fin n) ℂ)
    (hcomm : Commute (Matrix.conjTranspose M) M) :
    ∀ i, ∑ k, ‖M k i‖ ^ 2 = ∑ k, ‖M i k‖ ^ 2 := by
  intro i
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

-- Upper-triangular + the column/row squared-norm identity ⇒ diagonal, by strong
-- induction on the row value with two abstract, strictly-smaller sub-lemmas.
--   * Combinator: strong induction on `i.val` (`Nat.strong_induction_on`) supplies, at
--     row `i`, that every earlier row is already diagonal (`ihrows`).
--   * `col_sum_collapse` — column `i`'s squared-norm sum collapses to `‖M i i‖²`
--     (earlier rows + triangularity kill every off-diagonal entry). A plain ℝ-sum
--     identity, not `IsDiag`.
--   * `sum_norm_sq_eq_single_imp_zero` — an abstract vector fact: if `∑ ‖f k‖²` equals
--     its `i`-th term, every other `f k` vanishes. No matrix in sight.
--   Glue: feed `hcol` through `hsum i` to get the row sum `= ‖M i i‖²`, then the vector
--   lemma forces row `i`'s off-diagonal entries to zero.
theorem triangular_rowcol_eq_imp_diag {n : ℕ} (M : Matrix (Fin n) (Fin n) ℂ)
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

-- Upper-triangular + normal ⇒ diagonal, split into a normality-extraction
-- and the triangular induction crux.
--   * `row_col_norm_eq` — from `Commute Mᴴ M`, equate diagonal entries of MᴴM and
--     MMᴴ to get the column-vs-row squared-norm identity `∑‖M k i‖² = ∑‖M i k‖²`.
--   * `triangular_rowcol_eq_imp_diag` — pure crux: triangular + that norm identity
--     forces off-diagonal entries to zero (strong induction on the row).
-- They combine directly: feed `htri` and the norm identity into the matrix lemma.
theorem matrix_core {n : ℕ} (M : Matrix (Fin n) (Fin n) ℂ)
    (htri : M.BlockTriangular id) (hcomm : Commute (Matrix.conjTranspose M) M) :
    M.IsDiag := by
  have h_rc : ∀ i, ∑ k, ‖M k i‖ ^ 2 = ∑ k, ‖M i k‖ ^ 2 := row_col_norm_eq M hcomm
  exact triangular_rowcol_eq_imp_diag M htri h_rc

end Library.LinearAlgebra.NormalDiagonalization.MatrixNorm
