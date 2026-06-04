import Library.LinearAlgebra.SchurTriangularization.FlagRank
import Library.LinearAlgebra.SchurTriangularization.InvariantSubspace
import Mathlib

open Library.LinearAlgebra.SchurTriangularization.FlagRank
open Library.LinearAlgebra.SchurTriangularization.InvariantSubspace

namespace Library.LinearAlgebra.SchurTriangularization.InvariantFlag

-- Two-step packaging: (1) `saturated_one_step_extension` lifts the rank-constrained
-- one-step extension hypothesis to all T-invariant subspaces (returning U itself
-- when U is full rank), giving `finrank U' = min (finrank U + 1) (finrank V)`.
-- (2) `iterate_extension_to_flag` recursively iterates that saturated extension
-- from ⊥ to build the flag W : ℕ → Submodule K V and verify the four properties.
-- Both sub-goals are pure linear algebra over a Field; the alg-closed input was
-- already consumed by the parent in producing h_ext.
theorem build_flag_by_iterated_extension :
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

-- Decompose into (1) a one-step extension lemma — any T-invariant subspace
-- of strictly smaller dimension can be enlarged to a T-invariant subspace
-- one dimension bigger (this is where alg-closedness enters, via an
-- eigenvalue of the induced endomorphism on V/U) — and (2) a pure-
-- linear-algebra packaging step that iterates such an extension starting
-- from ⊥ to build the full flag W : ℕ → Submodule K V with the four
-- properties. Sub-goal (1) carries the eigenvalue extraction;
-- sub-goal (2) handles the recursive flag assembly and rank arithmetic
-- with no alg-closed hypothesis.
theorem invariant_flag_exists :
    ∀ {K : Type*} [Field K] [IsAlgClosed K]
      {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
      (T : V →ₗ[K] V),
    ∃ W : ℕ → Submodule K V,
      W 0 = ⊥ ∧
      (∀ i, W i ≤ W (i + 1)) ∧
      (∀ i, Module.finrank K (W i) = min i (Module.finrank K V)) ∧
      (∀ i, ∀ v ∈ W i, T v ∈ W i)  := by
  intro K _ _ V _ _ _ T
  have h_extend := fun U hU hlt => extend_invariant_subspace T U hU hlt
  exact build_flag_by_iterated_extension T h_extend

end Library.LinearAlgebra.SchurTriangularization.InvariantFlag
