import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs

namespace Problems.LinearAlgebra.jordan_normal_form

-- entry_kind: Builder
-- jordan_add_const_diag: adding c•1 to a zero-diagonal Jordan matrix preserves Jordan form
-- Off-diagonal entries are unchanged (identity is 0 off-diagonal); diagonal entries all become c,
-- so the super-diagonal adjacency condition M i i = M j j lifts to c = c.
theorem jordan_add_const_diag
    {n : ℕ} {K : Type*} [Field K]
    (M : Matrix (Fin n) (Fin n) K) (c : K)
    (hJF : IsJordanForm M) (hdiag : ∀ i, M i i = 0) :
    IsJordanForm (M + c • 1) := by
  unfold IsJordanForm at *
  intro i j
  simp only [Matrix.add_apply, Matrix.smul_apply, Matrix.one_apply, smul_eq_mul]
  have hM := hJF i j
  by_cases h1 : (i : ℕ) = (j : ℕ)
  · simp [h1]
  · simp only [if_neg h1] at hM
    have hne : i ≠ j := Fin.val_ne_iff.mp h1
    simp only [if_neg h1, if_neg hne, mul_zero, add_zero]
    by_cases h2 : (i : ℕ) + 1 = (j : ℕ)
    · simp only [if_pos h2] at hM
      simp only [if_pos h2]
      cases hM with
      | inl h => left; exact h
      | inr h => right; exact ⟨h.1, by rw [hdiag i, hdiag j]⟩
    · simp only [if_neg h2] at hM
      simp only [if_neg h2]
      exact hM

end Problems.LinearAlgebra.jordan_normal_form
