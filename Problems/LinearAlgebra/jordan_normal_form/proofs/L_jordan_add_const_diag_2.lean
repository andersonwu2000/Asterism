import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs

namespace Problems.LinearAlgebra.jordan_normal_form

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

end Problems.LinearAlgebra.jordan_normal_form