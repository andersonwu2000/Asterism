import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs

namespace Problems.LinearAlgebra.jordan_normal_form

-- entry_kind: Backward
theorem succ_descent_step
    {K W : Type*} [Field K] [AddCommGroup W] [Module K W] [FiniteDimensional K W]
    (N : W →ₗ[K] W) (hN : IsNilpotent N) {m : ℕ} (hdim : Module.finrank K W ≤ m + 1)
    (ih : ∀ {W' : Type*} [AddCommGroup W'] [Module K W'] [FiniteDimensional K W']
            (N' : W' →ₗ[K] W'), IsNilpotent N' → Module.finrank K W' ≤ m →
            ∃ b : Module.Basis (Fin (Module.finrank K W')) K W',
              ∀ j : Fin (Module.finrank K W'),
                N' (b j) = 0 ∨
                  ∃ i : Fin (Module.finrank K W'),
                    (i : ℕ) + 1 = (j : ℕ) ∧ N' (b j) = b i) :
    ∃ b : Module.Basis (Fin (Module.finrank K W)) K W,
      ∀ j : Fin (Module.finrank K W),
        N (b j) = 0 ∨
          ∃ i : Fin (Module.finrank K W),
            (i : ℕ) + 1 = (j : ℕ) ∧ N (b j) = b i := by sorry

end Problems.LinearAlgebra.jordan_normal_form
