import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_chain_permutation_exists

namespace Problems.LinearAlgebra.jordan_normal_form
-- Decompose into a single combinatorial sub-goal: existence of a permutation
-- σ : Fin n ≃ Fin n that lines up the chains-induced-by-π on consecutive indices.
-- Closure here is pure reindex bookkeeping: with b' := b.reindex σ.symm we have
-- b' j = b (σ j), so N(b' j) = N(b(σ j)) is either 0 (chain leaf) or b i = b'(σ.symm i)
-- where σ.symm i + 1 = j by the permutation's property.
theorem s10890
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
            (i : ℕ) + 1 = (j : ℕ) ∧ N (b' j) = b' i  := by
  obtain ⟨σ, hσ⟩ := chain_permutation_exists N b π hπ
  refine ⟨b.reindex σ.symm, ?_⟩
  intro j
  rcases hπ (σ j) with ⟨_, hN⟩ | ⟨i, hsome, hN⟩
  · left
    have : (b.reindex σ.symm) j = b (σ j) := by
      simp [Module.Basis.reindex_apply]
    rw [this, hN]
  · right
    refine ⟨σ.symm i, hσ j i hsome, ?_⟩
    have e1 : (b.reindex σ.symm) j = b (σ j) := by
      simp [Module.Basis.reindex_apply]
    have e2 : (b.reindex σ.symm) (σ.symm i) = b i := by
      simp [Module.Basis.reindex_apply]
    rw [e1, e2, hN]


end Problems.LinearAlgebra.jordan_normal_form
