import Mathlib
import Problems.LinearAlgebra.schur_triangularization.Defs
import Problems.LinearAlgebra.schur_triangularization.proofs.L_extension_iteration_sequence
import Problems.LinearAlgebra.schur_triangularization.proofs.L_rank_chain_min_eq

namespace Problems.LinearAlgebra.schur_triangularization

-- Two-step packaging: (1) `extension_iteration_sequence` constructs the recursive
-- flag W : ℕ → Submodule K V from the saturated one-step extension hypothesis,
-- giving W 0 = ⊥, the chain, T-invariance at every level, and the *step* rank
-- equation `finrank (W (i+1)) = min (finrank (W i) + 1) (finrank V)`.
-- (2) `rank_chain_min_eq` is a pure ℕ-induction lemma converting that step rank
-- equation, together with W 0 = ⊥, into the closed-form `finrank (W i) = min i (finrank V)`.
theorem s10844 :
    ∀ {K : Type*} [Field K]
      {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
      (T : V →ₗ[K] V),
      (∀ (U : Submodule K V), (∀ v ∈ U, T v ∈ U) →
        ∃ U' : Submodule K V, U ≤ U' ∧ (∀ v ∈ U', T v ∈ U') ∧
          Module.finrank K U' = min (Module.finrank K U + 1) (Module.finrank K V)) →
      ∃ W : ℕ → Submodule K V,
        W 0 = ⊥ ∧
        (∀ i, W i ≤ W (i + 1)) ∧
        (∀ i, Module.finrank K (W i) = min i (Module.finrank K V)) ∧
        (∀ i, ∀ v ∈ W i, T v ∈ W i)  := by
  intro K _ V _ _ _ T h_ext
  have h_seq := extension_iteration_sequence T h_ext
  have h_rank := rank_chain_min_eq T h_ext
  obtain ⟨W, hW0, hW_le, hW_inv, hW_step⟩ := h_seq
  exact ⟨W, hW0, hW_le, h_rank W hW0 hW_step, hW_inv⟩
end Problems.LinearAlgebra.schur_triangularization
