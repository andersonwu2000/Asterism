import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs

namespace Problems.LinearAlgebra.jordan_normal_form

-- entry_kind: Backward
theorem nilpotent_chain_pair_basis_exists
    {K W : Type*} [Field K] [AddCommGroup W] [Module K W] [FiniteDimensional K W]
    (N : W →ₗ[K] W) (hN : IsNilpotent N) :
    ∃ (b : Module.Basis (Fin (Module.finrank K W)) K W)
      (π : Fin (Module.finrank K W) → Option (Fin (Module.finrank K W))),
      ∀ j : Fin (Module.finrank K W),
        (π j = none ∧ N (b j) = 0) ∨
        (∃ i, π j = some i ∧ N (b j) = b i) := by sorry

end Problems.LinearAlgebra.jordan_normal_form
