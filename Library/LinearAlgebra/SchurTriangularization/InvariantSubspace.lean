import Library.LinearAlgebra.SchurTriangularization.QuotientEigenvalue
import Library.LinearAlgebra.SchurTriangularization.SubmoduleLemmas
import Mathlib

open Library.LinearAlgebra.SchurTriangularization.QuotientEigenvalue
open Library.LinearAlgebra.SchurTriangularization.SubmoduleLemmas

namespace Library.LinearAlgebra.SchurTriangularization.InvariantSubspace

-- Pick witness U' := U ⊔ span {v}. Inclusion U ≤ U' is `le_sup_left`.
-- Sub-goal (a) `sup_span_singleton_invariant`: T-invariance of U' uses hTU and
-- `T v - μ • v ∈ U` to land `T v = μ • v + (T v - μ • v)` back in U'.
-- Sub-goal (b) `sup_span_singleton_finrank`: rank jumps by one because v ∉ U.
theorem extend_via_near_eigenvector :
    ∀ {K : Type*} [Field K]
      {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
      (T : V →ₗ[K] V) (U : Submodule K V) (v : V) (μ : K),
      (∀ w ∈ U, T w ∈ U) →
      v ∉ U →
      T v - μ • v ∈ U →
      ∃ U' : Submodule K V, U ≤ U' ∧ (∀ w ∈ U', T w ∈ U') ∧
        Module.finrank K U' = Module.finrank K U + 1  := by
  intro K _ V _ _ _ T U v μ hTU hv hμ
  have h_inv := sup_span_singleton_invariant T U v μ hTU hμ
  have h_rank := sup_span_singleton_finrank U v hv
  exact ⟨U ⊔ Submodule.span K {v}, le_sup_left, h_inv, h_rank⟩

-- Split the one-step T-invariant extension into (A) producing a quotient-eigenvector
-- lift `v ∉ U` with `T v - μ • v ∈ U` for some μ — this is where IsAlgClosed enters,
-- via the induced endomorphism on V/U having an eigenvalue — and (B) a pure
-- linear-algebra step that turns any such (v, μ) into `U' = U ⊔ span{v}`,
-- T-invariant of dim `finrank U + 1`. Sub-goal (B) is alg-closed-free.
theorem extend_invariant_subspace :
    ∀ {K : Type*} [Field K] [IsAlgClosed K]
      {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
      (T : V →ₗ[K] V) (U : Submodule K V),
      (∀ v ∈ U, T v ∈ U) →
      Module.finrank K U < Module.finrank K V →
      ∃ U' : Submodule K V, U ≤ U' ∧ (∀ v ∈ U', T v ∈ U') ∧
        Module.finrank K U' = Module.finrank K U + 1  := by
  intro K _ _ V _ _ _ T U hU hlt
  obtain ⟨v, hv, μ, hμ⟩ := quotient_has_eigenvector_lift T U hU hlt
  exact extend_via_near_eigenvector T U v μ hU hv hμ

end Library.LinearAlgebra.SchurTriangularization.InvariantSubspace
