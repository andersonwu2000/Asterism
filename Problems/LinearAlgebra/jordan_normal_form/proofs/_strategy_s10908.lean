import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_block_membership
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_collected_repr_off_block_zero

namespace Problems.LinearAlgebra.jordan_normal_form

-- Off-diagonal block of `T` in the collected eigenbasis vanishes (μ₁ ≠ μ₂).
-- `block_membership`: `T (collectedBasis ⟨μ₂,j⟩)` stays in the μ₂ generalized eigenspace.
-- `collected_repr_off_block_zero`: the collected-basis coordinate of any vector of the
--   μ₂ summand at a μ₁-index (μ₁ ≠ μ₂) is `0` (direct-sum independence).
-- Combine: unfold the matrix entry via `LinearMap.toMatrix_apply`, then the repr lemma
--   applied to the membership fact closes it.
theorem s10908
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
    (μ₁ μ₂ : K) (h : μ₁ ≠ μ₂)
    (i : Fin (Module.finrank K (Module.End.maxGenEigenspace T μ₁ : Submodule K V)))
    (j : Fin (Module.finrank K (Module.End.maxGenEigenspace T μ₂ : Submodule K V))) :
    LinearMap.toMatrix (hdec.collectedBasis bμ) (hdec.collectedBasis bμ) T ⟨μ₁, i⟩ ⟨μ₂, j⟩ = 0  := by
  have hmem : T ((hdec.collectedBasis bμ) ⟨μ₂, j⟩) ∈
      (Module.End.maxGenEigenspace T μ₂ : Submodule K V) :=
    block_membership T hdec hinv bμ μ₂ j
  rw [LinearMap.toMatrix_apply]
  exact collected_repr_off_block_zero T hdec hinv bμ μ₁ μ₂ h i
    (T ((hdec.collectedBasis bμ) ⟨μ₂, j⟩)) hmem

end Problems.LinearAlgebra.jordan_normal_form
