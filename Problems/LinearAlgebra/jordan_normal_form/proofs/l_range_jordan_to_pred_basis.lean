import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs

namespace Problems.LinearAlgebra.jordan_normal_form

-- entry_kind: Backward
theorem range_jordan_to_pred_basis
    {K W : Type*} [Field K] [AddCommGroup W] [Module K W] [FiniteDimensional K W]
    (N : W →ₗ[K] W) (hN : IsNilpotent N) (hN0 : N ≠ 0)
    (h_inv : ∀ x ∈ LinearMap.range N, N x ∈ LinearMap.range N)
    (bU : Module.Basis (Fin (Module.finrank K (LinearMap.range N))) K (LinearMap.range N))
    (hbU : ∀ j : Fin (Module.finrank K (LinearMap.range N)),
        (N.restrict h_inv) (bU j) = 0 ∨
          ∃ i : Fin (Module.finrank K (LinearMap.range N)),
            (i : ℕ) + 1 = (j : ℕ) ∧ (N.restrict h_inv) (bU j) = bU i) :
    ∃ (b : Module.Basis (Fin (Module.finrank K W)) K W)
      (π : Fin (Module.finrank K W) → Option (Fin (Module.finrank K W))),
      ∀ j : Fin (Module.finrank K W),
        (π j = none ∧ N (b j) = 0) ∨
        (∃ i, π j = some i ∧ N (b j) = b i) := by sorry

end Problems.LinearAlgebra.jordan_normal_form
