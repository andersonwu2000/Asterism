import Mathlib
import Problems.LinearAlgebra.schur_triangularization.Defs
import Problems.LinearAlgebra.schur_triangularization.proofs.L_sup_span_singleton_finrank
import Problems.LinearAlgebra.schur_triangularization.proofs.L_sup_span_singleton_invariant

namespace Problems.LinearAlgebra.schur_triangularization

-- Pick witness U' := U ⊔ span {v}. Inclusion U ≤ U' is `le_sup_left`.
-- Sub-goal (a) `sup_span_singleton_invariant`: T-invariance of U' uses hTU and
-- `T v - μ • v ∈ U` to land `T v = μ • v + (T v - μ • v)` back in U'.
-- Sub-goal (b) `sup_span_singleton_finrank`: rank jumps by one because v ∉ U.
theorem s10842 :
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
end Problems.LinearAlgebra.schur_triangularization
