import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs

namespace Problems.LinearAlgebra.jordan_normal_form

-- entry_kind: Builder
theorem to_matrix_add_smul_one_2
    {n : ℕ} {K : Type*} [Field K]
    {W : Type*} [AddCommGroup W] [Module K W]
    (b : Module.Basis (Fin n) K W) (N : W →ₗ[K] W) (μ : K) :
    LinearMap.toMatrix b b (N + μ • 1) = LinearMap.toMatrix b b N + μ • 1 := by norm_num

end Problems.LinearAlgebra.jordan_normal_form
