import Mathlib
import Problems.LinearAlgebra.schur_triangularization.Defs
import Problems.LinearAlgebra.schur_triangularization.proofs.L_build_flag_by_iterated_extension
import Problems.LinearAlgebra.schur_triangularization.proofs.L_extend_invariant_subspace

namespace Problems.LinearAlgebra.schur_triangularization

-- Decompose into (1) a one-step extension lemma — any T-invariant subspace
-- of strictly smaller dimension can be enlarged to a T-invariant subspace
-- one dimension bigger (this is where alg-closedness enters, via an
-- eigenvalue of the induced endomorphism on V/U) — and (2) a pure-
-- linear-algebra packaging step that iterates such an extension starting
-- from ⊥ to build the full flag W : ℕ → Submodule K V with the four
-- properties. Sub-goal (1) carries the eigenvalue extraction;
-- sub-goal (2) handles the recursive flag assembly and rank arithmetic
-- with no alg-closed hypothesis.
theorem s10837 :
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

end Problems.LinearAlgebra.schur_triangularization
