import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs

namespace Problems.LinearAlgebra.jordan_normal_form

-- entry_kind: Builder
theorem zero_index_maps_to_zero
    {K W : Type*} [Field K] [AddCommGroup W] [Module K W] [FiniteDimensional K W]
    (N : W →ₗ[K] W)
    (h_inv : ∀ x ∈ LinearMap.range N, N x ∈ LinearMap.range N)
    (bU : Module.Basis (Fin (Module.finrank K (LinearMap.range N))) K (LinearMap.range N))
    (hbU : ∀ j : Fin (Module.finrank K (LinearMap.range N)),
        (N.restrict h_inv) (bU j) = 0 ∨
          ∃ i : Fin (Module.finrank K (LinearMap.range N)),
            (i : ℕ) + 1 = (j : ℕ) ∧ (N.restrict h_inv) (bU j) = bU i) :
    ∀ q : Fin (Module.finrank K (LinearMap.range N)),
        (q : ℕ) = 0 → (N.restrict h_inv) (bU q) = 0 := by grind

end Problems.LinearAlgebra.jordan_normal_form
