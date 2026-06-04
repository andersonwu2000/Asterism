import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs

namespace Problems.LinearAlgebra.jordan_normal_form

-- entry_kind: Builder
-- block_membership: T maps each collectedBasis vector of the μ₂-eigenspace into that eigenspace.
-- Uses collectedBasis_coe to reduce to a subtype element, then applies invariance via hinv.
theorem block_membership
    {K : Type*} [Field K] [DecidableEq K]
    {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
    (T : V →ₗ[K] V)
    (hdec : DirectSum.IsInternal
      (fun μ : K => (Module.End.maxGenEigenspace T μ : Submodule K V)))
    (hinv : ∀ μ : K, ∀ x ∈ (Module.End.maxGenEigenspace T μ : Submodule K V),
        T x ∈ (Module.End.maxGenEigenspace T μ : Submodule K V))
    (bμ : ∀ μ : K, Module.Basis
        (Fin (Module.finrank K (Module.End.maxGenEigenspace T μ : Submodule K V))) K
        (Module.End.maxGenEigenspace T μ : Submodule K V))
    (μ₂ : K)
    (j : Fin (Module.finrank K (Module.End.maxGenEigenspace T μ₂ : Submodule K V))) :
    T ((hdec.collectedBasis bμ) ⟨μ₂, j⟩) ∈
      (Module.End.maxGenEigenspace T μ₂ : Submodule K V) := by
  apply hinv
  rw [hdec.collectedBasis_coe]
  exact (bμ μ₂ j).2

end Problems.LinearAlgebra.jordan_normal_form
