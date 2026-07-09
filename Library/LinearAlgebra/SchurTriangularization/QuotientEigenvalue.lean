import Library.LinearAlgebra.SchurTriangularization.SubmoduleLemmas
import Mathlib

open Library.LinearAlgebra.SchurTriangularization.SubmoduleLemmas

namespace Library.LinearAlgebra.SchurTriangularization.QuotientEigenvalue

-- Descend `T` to `F : V ⧸ U →ₗ[K] V ⧸ U` via `Submodule.mapQ` (using
-- `U`-invariance recast as `U ≤ comap T U`), apply `Module.End.exists_eigenvalue`
-- to the finite-dimensional nontrivial `V ⧸ U` over the algebraically closed `K`
-- to obtain `(μ, w)` with `F w = μ • w` and `w ≠ 0`, then lift `w` along
-- `U.mkQ_surjective` to `v ∈ V` and translate via `Submodule.mapQ_apply`.
theorem exists_eigenvalue_witness_on_quotient :
    ∀ {K : Type*} [Field K] [IsAlgClosed K]
      {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
      (T : V →ₗ[K] V) (U : Submodule K V),
      (∀ v ∈ U, T v ∈ U) → Nontrivial (V ⧸ U) →
      ∃ μ : K, ∃ v : V, U.mkQ v ≠ 0 ∧ U.mkQ (T v) = μ • U.mkQ v  := by
  intros K _ _ V _ _ _ T U h_inv h_nontriv
  have hUU : U ≤ Submodule.comap T U := by
    intro x hx
    exact h_inv x hx
  let F : V ⧸ U →ₗ[K] V ⧸ U := Submodule.mapQ U U T hUU
  obtain ⟨μ, hμ⟩ := Module.End.exists_eigenvalue F
  obtain ⟨w, hw⟩ := hμ.exists_hasEigenvector
  obtain ⟨v, hv⟩ := U.mkQ_surjective w
  refine ⟨μ, v, ?_, ?_⟩
  · rw [hv]; exact hw.2
  · have hmapq : F (U.mkQ v) = U.mkQ (T v) := by
      simp [F, Submodule.mapQ_apply]
    rw [← hmapq, hv]; exact hw.apply_eq_smul

-- near_eigenvector_of_quotient_eigenvector: quotient algebra translates a quotient eigenvector
-- witness back to v ∉ U and T v - μ • v ∈ U via mk_eq_zero and linearity of mkQ.
theorem near_eigenvector_of_quotient_eigenvector :
    ∀ {K : Type*} [Field K]
      {V : Type*} [AddCommGroup V] [Module K V]
      (T : V →ₗ[K] V) (U : Submodule K V) (μ : K) (v : V),
      U.mkQ v ≠ 0 → U.mkQ (T v) = μ • U.mkQ v →
      v ∉ U ∧ T v - μ • v ∈ U := by
  intro K _instField V _instACG _instMod T U μ v h1 h2
  refine ⟨fun hv => ?_, ?_⟩
  · exact h1 (by simp [hv])
  · have : U.mkQ (T v - μ • v) = 0 := by
      simp [map_sub, map_smul, h2]
    rwa [← LinearMap.mem_ker, Submodule.ker_mkQ] at this

-- Split the quotient-eigenvector lift into (A) `Nontrivial (V ⧸ U)` from the finrank gap,
-- (B) algebraic-closedness gives the induced endomorphism on `V ⧸ U` an eigenvalue with a
-- nonzero quotient witness, and (C) pure quotient algebra translates any such witness
-- back to `v ∉ U` together with `T v - μ • v ∈ U`. Only (B) uses `IsAlgClosed`.
theorem quotient_has_eigenvector_lift :
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

end Library.LinearAlgebra.SchurTriangularization.QuotientEigenvalue
