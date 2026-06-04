import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs

namespace Problems.LinearAlgebra.jordan_normal_form

-- entry_kind: Backward
theorem chain_permutation_exists
    {K W : Type*} [Field K] [AddCommGroup W] [Module K W] [FiniteDimensional K W]
    (N : W →ₗ[K] W)
    (b : Module.Basis (Fin (Module.finrank K W)) K W)
    (π : Fin (Module.finrank K W) → Option (Fin (Module.finrank K W)))
    (hπ : ∀ j : Fin (Module.finrank K W),
      (π j = none ∧ N (b j) = 0) ∨
      (∃ i, π j = some i ∧ N (b j) = b i)) :
    ∃ σ : Fin (Module.finrank K W) ≃ Fin (Module.finrank K W),
      ∀ j : Fin (Module.finrank K W), ∀ i : Fin (Module.finrank K W),
        π (σ j) = some i → ((σ.symm i : ℕ) + 1 = (j : ℕ)) := by sorry

end Problems.LinearAlgebra.jordan_normal_form
