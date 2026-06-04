import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_jordan_add_const_diag_2
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_to_matrix_add_smul_one_2

namespace Problems.LinearAlgebra.jordan_normal_form

-- Adding μ•1 to a zero-diagonal Jordan matrix preserves Jordan form, via toMatrix linearity.
-- Sub-goals: (1) `to_matrix_add_smul_one_2` — toMatrix distributes the μ•1 shift;
-- (2) `jordan_add_const_diag_2` — adding c•1 to a zero-diagonal Jordan matrix stays Jordan.
-- Closer rewrites the toMatrix expression and applies the matrix-level shift fact.
theorem s11031
    {n : ℕ} {K : Type*} [Field K]
    {W : Type*} [AddCommGroup W] [Module K W]
    (b : Module.Basis (Fin n) K W) (N : W →ₗ[K] W) (μ : K)
    (hJF : IsJordanForm (LinearMap.toMatrix b b N))
    (hdiag : ∀ i, (LinearMap.toMatrix b b N) i i = 0) :
    IsJordanForm (LinearMap.toMatrix b b (N + μ • 1))  := by
  have h_to_matrix := to_matrix_add_smul_one_2 b N μ
  have h_jordan_shift := jordan_add_const_diag_2 (LinearMap.toMatrix b b N) μ hJF hdiag
  rw [h_to_matrix]; exact h_jordan_shift

end Problems.LinearAlgebra.jordan_normal_form
