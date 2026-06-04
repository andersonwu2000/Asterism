import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs

namespace Problems.LinearAlgebra.jordan_normal_form

-- Entrywise (μ,μ)-diagonal block of the collected-basis matrix.
-- Unfold both `toMatrix` entries; the basis vector `collectedBasis ⟨μ,j⟩` is `↑(bμ μ j)`
-- and `T ↑(bμ μ j) = ↑((T.restrict).._)` by `restrict_apply`; the coordinate of a single-
-- summand element under the collected basis equals its `bμ μ`-coordinate (bridge `hbridge`).
theorem s10907
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
    [Fintype ((μ : K) × Fin (Module.finrank K (Module.End.maxGenEigenspace T μ : Submodule K V)))]
    (μ : K)
    (i j : Fin (Module.finrank K (Module.End.maxGenEigenspace T μ : Submodule K V))) :
    LinearMap.toMatrix (hdec.collectedBasis bμ) (hdec.collectedBasis bμ) T ⟨μ, i⟩ ⟨μ, j⟩
      = LinearMap.toMatrix (bμ μ) (bμ μ) (T.restrict (hinv μ)) i j  := by
  have hbridge : ∀ (w : (Module.End.maxGenEigenspace T μ : Submodule K V))
      (k : Fin (Module.finrank K (Module.End.maxGenEigenspace T μ : Submodule K V))),
      (hdec.collectedBasis bμ).repr (w : V) ⟨μ, k⟩ = (bμ μ).repr w k := by
    intro w k
    let L1 : (Module.End.maxGenEigenspace T μ : Submodule K V) →ₗ[K] K :=
      (Finsupp.lapply
          (⟨μ, k⟩ : (ν : K) ×
            Fin (Module.finrank K (Module.End.maxGenEigenspace T ν : Submodule K V)))).comp
        (((hdec.collectedBasis bμ).repr.toLinearMap).comp
          (Module.End.maxGenEigenspace T μ : Submodule K V).subtype)
    let L2 : (Module.End.maxGenEigenspace T μ : Submodule K V) →ₗ[K] K :=
      (Finsupp.lapply k).comp (bμ μ).repr.toLinearMap
    have hL : L1 = L2 := by
      apply (bμ μ).ext
      intro k'
      simp only [L1, L2, LinearMap.comp_apply, Finsupp.lapply_apply, Submodule.subtype_apply,
        LinearEquiv.coe_coe]
      rw [show ((bμ μ) k' : V) = (hdec.collectedBasis bμ) ⟨μ, k'⟩ from
        (hdec.collectedBasis_coe bμ ▸ rfl)]
      rw [Module.Basis.repr_self_apply, Module.Basis.repr_self_apply]
      simp [Sigma.mk.injEq]
    have := congrArg (fun L => L w) hL
    simpa [L1, L2] using this
  rw [LinearMap.toMatrix_apply, LinearMap.toMatrix_apply, hdec.collectedBasis_coe]
  have hTcoe : T ((bμ μ j : V)) = ((T.restrict (hinv μ)) (bμ μ j) : V) := by
    rw [LinearMap.restrict_apply]
  rw [hTcoe]
  exact hbridge ((T.restrict (hinv μ)) (bμ μ j)) i


end Problems.LinearAlgebra.jordan_normal_form
