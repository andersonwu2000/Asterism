import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_block_enum

namespace Problems.LinearAlgebra.jordan_normal_form

theorem s10926
    {K W : Type*} [Field K] [AddCommGroup W] [Module K W] [FiniteDimensional K W]
    (N : W →ₗ[K] W)
    (r : ℕ) (k : Fin r → ℕ)
    (c : Module.Basis (Σ s : Fin r, Fin (k s)) K W)
    (hc : ∀ (s : Fin r) (j : Fin (k s)),
        N (c ⟨s, j⟩) = 0 ∨
          ∃ i : Fin (k s), (i : ℕ) + 1 = (j : ℕ) ∧ N (c ⟨s, j⟩) = c ⟨s, i⟩) :
    ∃ b : Module.Basis (Fin (Module.finrank K W)) K W,
      ∀ j : Fin (Module.finrank K W),
        N (b j) = 0 ∨
          ∃ i : Fin (Module.finrank K W),
            (i : ℕ) + 1 = (j : ℕ) ∧ N (b j) = b i := by sorry
end Problems.LinearAlgebra.jordan_normal_form
