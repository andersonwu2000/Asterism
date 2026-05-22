import Mathlib
import Problems.LinearAlgebra.schur_triangularization.Defs
import Problems.LinearAlgebra.schur_triangularization.proofs.L_extend_via_near_eigenvector
import Problems.LinearAlgebra.schur_triangularization.proofs.L_quotient_has_eigenvector_lift

namespace Problems.LinearAlgebra.schur_triangularization

-- Split the one-step T-invariant extension into (A) producing a quotient-eigenvector
-- lift `v ∉ U` with `T v - μ • v ∈ U` for some μ — this is where IsAlgClosed enters,
-- via the induced endomorphism on V/U having an eigenvalue — and (B) a pure
-- linear-algebra step that turns any such (v, μ) into `U' = U ⊔ span{v}`,
-- T-invariant of dim `finrank U + 1`. Sub-goal (B) is alg-closed-free.
theorem s10839 :
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

end Problems.LinearAlgebra.schur_triangularization
