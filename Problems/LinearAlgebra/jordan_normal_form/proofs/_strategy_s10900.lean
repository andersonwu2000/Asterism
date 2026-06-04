import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_jordan_add_const_diag
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_to_matrix_add_smul_one

namespace Problems.LinearAlgebra.jordan_normal_form

theorem s10900
    {n : ℕ} {K : Type*} [Field K]
    {W : Type*} [AddCommGroup W] [Module K W]
    (b : Module.Basis (Fin n) K W) (N : W →ₗ[K] W) (μ : K)
    (hJF : IsJordanForm (LinearMap.toMatrix b b N))
    (hdiag : ∀ i, (LinearMap.toMatrix b b N) i i = 0) :
    IsJordanForm (LinearMap.toMatrix b b (N + μ • 1)) := by sorry

end Problems.LinearAlgebra.jordan_normal_form
