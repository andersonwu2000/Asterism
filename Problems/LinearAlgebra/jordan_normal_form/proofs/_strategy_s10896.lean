import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_jordan_chain_basis_dim_induction

namespace Problems.LinearAlgebra.jordan_normal_form

-- Reduce to a strong-induction-ready generalized lemma: the same statement for an
-- arbitrary nilpotent operator on a space of dimension ≤ n (the bound `n` is the
-- well-founded measure for induction on `Module.finrank`, which cannot be run with the
-- ambient `W` fixed). The parent is the `n := finrank K W` instance.
-- The generalized lemma carries the textbook recursion (N = 0 base; `range N` descent).
theorem s10896
    {K W : Type*} [Field K] [AddCommGroup W] [Module K W] [FiniteDimensional K W]
    (N : W →ₗ[K] W) (hN : IsNilpotent N) :
    ∃ b : Module.Basis (Fin (Module.finrank K W)) K W,
      ∀ j : Fin (Module.finrank K W),
        N (b j) = 0 ∨
          ∃ i : Fin (Module.finrank K W),
            (i : ℕ) + 1 = (j : ℕ) ∧ N (b j) = b i  := by
  have h_chain := jordan_chain_basis_dim_induction N hN
  exact h_chain (Module.finrank K W) le_rfl

end Problems.LinearAlgebra.jordan_normal_form
