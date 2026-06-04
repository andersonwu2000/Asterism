import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs

namespace Problems.LinearAlgebra.jordan_normal_form

-- entry_kind: Builder
theorem range_restrict_nilpotent
    {K W : Type*} [Field K] [AddCommGroup W] [Module K W] [FiniteDimensional K W]
    (N : W →ₗ[K] W) (hN : IsNilpotent N)
    (h_inv : ∀ x ∈ LinearMap.range N, N x ∈ LinearMap.range N) :
    IsNilpotent (N.restrict h_inv) := by exact Module.End.isNilpotent.restrict h_inv hN

end Problems.LinearAlgebra.jordan_normal_form
