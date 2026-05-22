import Mathlib
import Problems.LinearAlgebra.schur_triangularization.Defs

namespace Problems.LinearAlgebra.schur_triangularization

-- Descend `T` to `F : V ⧸ U →ₗ[K] V ⧸ U` via `Submodule.mapQ` (using
-- `U`-invariance recast as `U ≤ comap T U`), apply `Module.End.exists_eigenvalue`
-- to the finite-dimensional nontrivial `V ⧸ U` over the algebraically closed `K`
-- to obtain `(μ, w)` with `F w = μ • w` and `w ≠ 0`, then lift `w` along
-- `U.mkQ_surjective` to `v ∈ V` and translate via `Submodule.mapQ_apply`.
theorem s10846 :
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

end Problems.LinearAlgebra.schur_triangularization
