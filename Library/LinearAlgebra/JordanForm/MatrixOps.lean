import Library.LinearAlgebra.JordanForm.Defs
import Mathlib

open Library.LinearAlgebra.JordanForm.Defs

namespace Library.LinearAlgebra.JordanForm.MatrixOps

-- jordan_add_const_diag_2: shifting a zero-diagonal Jordan matrix by c•1 preserves Jordan form
-- Off-diagonal entries are unchanged (identity is 0 there); diagonal entries both shift by c,
-- so the equal-diagonal condition M i i = M j j is preserved as c = c.
-- entry_kind: Builder
theorem jordan_add_const_diag_2
    {n : ℕ} {K : Type*} [Field K]
    (M : Matrix (Fin n) (Fin n) K) (c : K)
    (hJF : IsJordanForm M) (hdiag : ∀ i, M i i = 0) :
    IsJordanForm (M + c • 1) := by
  unfold IsJordanForm at hJF ⊢
  intro i j
  have hJFij := hJF i j
  by_cases hval : (i : ℕ) = (j : ℕ)
  · simp only [if_pos hval]
  · have hij : i ≠ j := Fin.ne_of_val_ne hval
    simp only [Matrix.add_apply, Matrix.smul_apply, Matrix.one_apply, if_neg hij,
               smul_zero, add_zero]
    simp only [if_neg hval] at hJFij
    by_cases hsup : (i : ℕ) + 1 = (j : ℕ)
    · simp only [if_neg hval, if_pos hsup]
      simp only [if_pos hsup] at hJFij
      rcases hJFij with h | ⟨h1, _⟩
      · left; exact h
      · right
        refine ⟨h1, ?_⟩
        simp [hdiag]
    · simp only [if_neg hval, if_neg hsup]
      simp only [if_neg hsup] at hJFij
      exact hJFij

-- entry_kind: Builder
theorem to_matrix_add_smul_one_2
    {n : ℕ} {K : Type*} [Field K]
    {W : Type*} [AddCommGroup W] [Module K W]
    (b : Module.Basis (Fin n) K W) (N : W →ₗ[K] W) (μ : K) :
    LinearMap.toMatrix b b (N + μ • 1) = LinearMap.toMatrix b b N + μ • 1 := by norm_num

-- Adding μ•1 to a zero-diagonal Jordan matrix preserves Jordan form, via toMatrix linearity.
-- Sub-goals: (1) `to_matrix_add_smul_one_2` — toMatrix distributes the μ•1 shift;
-- (2) `jordan_add_const_diag_2` — adding c•1 to a zero-diagonal Jordan matrix stays Jordan.
-- Closer rewrites the toMatrix expression and applies the matrix-level shift fact.
theorem jordan_form_add_smul_one
    {n : ℕ} {K : Type*} [Field K]
    {W : Type*} [AddCommGroup W] [Module K W]
    (b : Module.Basis (Fin n) K W) (N : W →ₗ[K] W) (μ : K)
    (hJF : IsJordanForm (LinearMap.toMatrix b b N))
    (hdiag : ∀ i, (LinearMap.toMatrix b b N) i i = 0) :
    IsJordanForm (LinearMap.toMatrix b b (N + μ • 1))  := by
  have h_to_matrix := to_matrix_add_smul_one_2 b N μ
  have h_jordan_shift := jordan_add_const_diag_2 (LinearMap.toMatrix b b N) μ hJF hdiag
  rw [h_to_matrix]; exact h_jordan_shift

end Library.LinearAlgebra.JordanForm.MatrixOps
