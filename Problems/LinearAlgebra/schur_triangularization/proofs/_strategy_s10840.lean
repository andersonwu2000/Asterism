import Mathlib
import Problems.LinearAlgebra.schur_triangularization.Defs
import Problems.LinearAlgebra.schur_triangularization.proofs.L_iterate_extension_to_flag
import Problems.LinearAlgebra.schur_triangularization.proofs.L_saturated_one_step_extension

namespace Problems.LinearAlgebra.schur_triangularization

-- Two-step packaging: (1) `saturated_one_step_extension` lifts the rank-constrained
-- one-step extension hypothesis to all T-invariant subspaces (returning U itself
-- when U is full rank), giving `finrank U' = min (finrank U + 1) (finrank V)`.
-- (2) `iterate_extension_to_flag` recursively iterates that saturated extension
-- from ⊥ to build the flag W : ℕ → Submodule K V and verify the four properties.
-- Both sub-goals are pure linear algebra over a Field; the alg-closed input was
-- already consumed by the parent in producing h_ext.
theorem s10840 :
    ∀ {K : Type*} [Field K]
      {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
      (T : V →ₗ[K] V),
      (∀ (U : Submodule K V), (∀ v ∈ U, T v ∈ U) →
        Module.finrank K U < Module.finrank K V →
        ∃ U' : Submodule K V, U ≤ U' ∧ (∀ v ∈ U', T v ∈ U') ∧
          Module.finrank K U' = Module.finrank K U + 1) →
      ∃ W : ℕ → Submodule K V,
        W 0 = ⊥ ∧
        (∀ i, W i ≤ W (i + 1)) ∧
        (∀ i, Module.finrank K (W i) = min i (Module.finrank K V)) ∧
        (∀ i, ∀ v ∈ W i, T v ∈ W i)  := by
  intro K _ V _ _ _ T h_ext
  have h_sat := saturated_one_step_extension T h_ext
  exact iterate_extension_to_flag T h_sat

end Problems.LinearAlgebra.schur_triangularization
