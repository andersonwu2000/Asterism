import Mathlib
import Problems.LinearAlgebra.schur_triangularization.Defs
import Problems.LinearAlgebra.schur_triangularization.proofs.L_exists_eigenvalue_witness_on_quotient
import Problems.LinearAlgebra.schur_triangularization.proofs.L_near_eigenvector_of_quotient_eigenvector
import Problems.LinearAlgebra.schur_triangularization.proofs.L_quotient_nontrivial_of_finrank_lt

namespace Problems.LinearAlgebra.schur_triangularization

-- Split the quotient-eigenvector lift into (A) `Nontrivial (V ⧸ U)` from the finrank gap,
-- (B) algebraic-closedness gives the induced endomorphism on `V ⧸ U` an eigenvalue with a
-- nonzero quotient witness, and (C) pure quotient algebra translates any such witness
-- back to `v ∉ U` together with `T v - μ • v ∈ U`. Only (B) uses `IsAlgClosed`.
theorem s10843 :
    ∀ {K : Type*} [Field K] [IsAlgClosed K]
      {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
      (T : V →ₗ[K] V) (U : Submodule K V),
      (∀ v ∈ U, T v ∈ U) →
      Module.finrank K U < Module.finrank K V →
      ∃ v : V, v ∉ U ∧ ∃ μ : K, T v - μ • v ∈ U  := by
  intro K _ _ V _ _ _ T U hTU hdim
  haveI h_nontriv : Nontrivial (V ⧸ U) := quotient_nontrivial_of_finrank_lt U hdim
  obtain ⟨μ, v, hv_ne, heig⟩ := exists_eigenvalue_witness_on_quotient T U hTU h_nontriv
  obtain ⟨hv_notU, hdiff⟩ := near_eigenvector_of_quotient_eigenvector T U μ v hv_ne heig
  exact ⟨v, hv_notU, μ, hdiff⟩

end Problems.LinearAlgebra.schur_triangularization
