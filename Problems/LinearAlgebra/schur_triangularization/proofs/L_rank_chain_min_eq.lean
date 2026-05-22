import Mathlib
import Problems.LinearAlgebra.schur_triangularization.Defs

namespace Problems.LinearAlgebra.schur_triangularization

-- entry_kind: Builder
-- rank_chain_min_eq: pure ℕ-induction converting step-rank equation to closed form
theorem rank_chain_min_eq :
    ∀ {K : Type*} [Field K]
      {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
      (T : V →ₗ[K] V),
      (∀ (U : Submodule K V), (∀ v ∈ U, T v ∈ U) →
        ∃ U' : Submodule K V, U ≤ U' ∧ (∀ v ∈ U', T v ∈ U') ∧
          Module.finrank K U' = min (Module.finrank K U + 1) (Module.finrank K V)) →
      ∀ (W : ℕ → Submodule K V),
      W 0 = ⊥ →
      (∀ i, Module.finrank K (W (i + 1)) =
        min (Module.finrank K (W i) + 1) (Module.finrank K V)) →
      ∀ i, Module.finrank K (W i) = min i (Module.finrank K V) := by
  intro K _ V _ _ _ T _hext W hW0 hWstep i
  induction i with
  | zero =>
    simp [hW0]
  | succ n ih =>
    rw [hWstep, ih]
    omega


end Problems.LinearAlgebra.schur_triangularization
