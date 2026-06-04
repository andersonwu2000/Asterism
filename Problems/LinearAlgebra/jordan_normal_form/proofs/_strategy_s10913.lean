import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs

namespace Problems.LinearAlgebra.jordan_normal_form

theorem s10913
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
    (μ₁ μ₂ : K) (h : μ₁ ≠ μ₂)
    (i : Fin (Module.finrank K (Module.End.maxGenEigenspace T μ₁ : Submodule K V)))
    (y : V) (hy : y ∈ (Module.End.maxGenEigenspace T μ₂ : Submodule K V)) :
    (hdec.collectedBasis bμ).repr y ⟨μ₁, i⟩ = 0  := by
  let L : (Module.End.maxGenEigenspace T μ₂ : Submodule K V) →ₗ[K] K :=
    (Finsupp.lapply
        (⟨μ₁, i⟩ : (ν : K) ×
          Fin (Module.finrank K (Module.End.maxGenEigenspace T ν : Submodule K V)))).comp
      (((hdec.collectedBasis bμ).repr.toLinearMap).comp
        (Module.End.maxGenEigenspace T μ₂ : Submodule K V).subtype)
  have hL : L = 0 := by
    apply (bμ μ₂).ext
    intro k'
    simp only [L, LinearMap.comp_apply, Finsupp.lapply_apply, Submodule.subtype_apply,
      LinearEquiv.coe_coe, LinearMap.zero_apply]
    rw [show ((bμ μ₂) k' : V) = (hdec.collectedBasis bμ) ⟨μ₂, k'⟩ from
      (hdec.collectedBasis_coe bμ ▸ rfl)]
    rw [Module.Basis.repr_self_apply]
    simp [Sigma.mk.injEq, Ne.symm h]
  have hy0 := congrArg (fun f => f ⟨y, hy⟩) hL
  simpa [L] using hy0

end Problems.LinearAlgebra.jordan_normal_form
