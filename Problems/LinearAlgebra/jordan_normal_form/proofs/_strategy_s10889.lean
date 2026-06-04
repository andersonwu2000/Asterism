import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_chain_pair_reorder_to_consecutive
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_nilpotent_chain_pair_basis_exists

namespace Problems.LinearAlgebra.jordan_normal_form

-- Decompose Jordan-chain basis existence into:
--   (1) existence of a chain-pair basis: a basis b plus a partial map π such that
--       N(b j) is either 0 (π j = none) or b i (π j = some i). This captures the
--       Jordan-chain structure as a forest (acyclic because N is nilpotent) without
--       constraining how chain elements are ordered along Fin n.
--   (2) reordering a chain-pair basis into one where consecutive indices form chains
--       in the form required by the parent goal — pure permutation bookkeeping, no
--       linear algebra beyond reindexing.
theorem s10889
    {K W : Type*} [Field K] [AddCommGroup W] [Module K W] [FiniteDimensional K W]
    (N : W →ₗ[K] W) (hN : IsNilpotent N) :
    ∃ b : Module.Basis (Fin (Module.finrank K W)) K W,
      ∀ j : Fin (Module.finrank K W),
        N (b j) = 0 ∨
          ∃ i : Fin (Module.finrank K W),
            (i : ℕ) + 1 = (j : ℕ) ∧ N (b j) = b i  := by
  obtain ⟨b₀, π, hπ⟩ := nilpotent_chain_pair_basis_exists N hN
  exact chain_pair_reorder_to_consecutive N b₀ π hπ

end Problems.LinearAlgebra.jordan_normal_form
