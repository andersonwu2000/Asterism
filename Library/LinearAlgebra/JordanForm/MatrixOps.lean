import Library.LinearAlgebra.JordanForm.Defs
import Mathlib

open Library.LinearAlgebra.JordanForm.Defs

/-!
# Matrix operations preserving Jordan form under scalar shifts

This file proves that adding a scalar multiple of the identity to a zero-diagonal Jordan matrix
preserves the Jordan form property, both at the matrix level and lifted through `LinearMap.toMatrix`.
-/

namespace Library.LinearAlgebra.JordanForm.MatrixOps

variable {n : ℕ} {K : Type*} [Field K]

/-- Shifting a zero-diagonal Jordan matrix `M` by `c • 1` preserves the Jordan form.
Off-diagonal entries are unchanged (the identity contributes 0 there), and the equal-diagonal
condition is maintained since both `M i i` and `M j j` shift by the same constant `c`. -/
theorem jordan_add_const_diag_2
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

section

variable {W : Type*} [AddCommGroup W] [Module K W]

/-- `LinearMap.toMatrix` distributes over the sum `N + μ • 1`, converting the scalar-identity
shift on the linear map side to a scalar-identity shift on the matrix side. -/
theorem to_matrix_add_smul_one_2
    (b : Module.Basis (Fin n) K W) (N : W →ₗ[K] W) (μ : K) :
    LinearMap.toMatrix b b (N + μ • 1) = LinearMap.toMatrix b b N + μ • 1 := by norm_num

/-- If `N` has a zero-diagonal Jordan-form matrix with respect to basis `b`, then `N + μ • 1`
also has a Jordan-form matrix. The proof applies `to_matrix_add_smul_one_2` to rewrite the
`toMatrix` expression, then uses `jordan_add_const_diag_2` for the matrix-level shift. -/
theorem jordan_form_add_smul_one
    (b : Module.Basis (Fin n) K W) (N : W →ₗ[K] W) (μ : K)
    (hJF : IsJordanForm (LinearMap.toMatrix b b N))
    (hdiag : ∀ i, (LinearMap.toMatrix b b N) i i = 0) :
    IsJordanForm (LinearMap.toMatrix b b (N + μ • 1)) := by
  have h_to_matrix := to_matrix_add_smul_one_2 b N μ
  have h_jordan_shift := jordan_add_const_diag_2 (LinearMap.toMatrix b b N) μ hJF hdiag
  rw [h_to_matrix]; exact h_jordan_shift

end

end Library.LinearAlgebra.JordanForm.MatrixOps
