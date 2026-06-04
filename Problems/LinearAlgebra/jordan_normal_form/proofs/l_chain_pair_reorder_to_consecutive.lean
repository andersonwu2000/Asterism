import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs

namespace Problems.LinearAlgebra.jordan_normal_form

-- entry_kind: Backward
theorem chain_pair_reorder_to_consecutive
    {K W : Type*} [Field K] [AddCommGroup W] [Module K W] [FiniteDimensional K W]
    (N : W →ₗ[K] W)
    (b : Module.Basis (Fin (Module.finrank K W)) K W)
    (π : Fin (Module.finrank K W) → Option (Fin (Module.finrank K W)))
    (hπ : ∀ j : Fin (Module.finrank K W),
      (π j = none ∧ N (b j) = 0) ∨
      (∃ i, π j = some i ∧ N (b j) = b i)) :
    ∃ b' : Module.Basis (Fin (Module.finrank K W)) K W,
      ∀ j : Fin (Module.finrank K W),
        N (b' j) = 0 ∨
          ∃ i : Fin (Module.finrank K W),
            (i : ℕ) + 1 = (j : ℕ) ∧ N (b' j) = b' i := by sorry

end Problems.LinearAlgebra.jordan_normal_form
