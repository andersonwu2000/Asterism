import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_diag_block
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_off_diag

namespace Problems.LinearAlgebra.jordan_normal_form

-- Entrywise: matrix of `T` in the collected basis is block-diagonal.
-- `diag_block`: the (μ,μ)-diagonal entry equals the restriction matrix entry.
-- `off_diag`: a (μ₁,μ₂)-entry with μ₁ ≠ μ₂ vanishes (T preserves each summand).
-- Combine via `Matrix.ext` + `by_cases μ₁ = μ₂` and `blockDiagonal'_apply_{eq,ne}`.
theorem s10905
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
    [Fintype ((μ : K) × Fin (Module.finrank K (Module.End.maxGenEigenspace T μ : Submodule K V)))] :
    LinearMap.toMatrix (hdec.collectedBasis bμ) (hdec.collectedBasis bμ) T
      = Matrix.blockDiagonal'
          (fun μ : K => LinearMap.toMatrix (bμ μ) (bμ μ) (T.restrict (hinv μ)))  := by
  apply Matrix.ext
  rintro ⟨μ₁, i⟩ ⟨μ₂, j⟩
  by_cases h : μ₁ = μ₂
  · subst h
    rw [Matrix.blockDiagonal'_apply_eq]
    exact diag_block T hdec hinv bμ μ₁ i j
  · rw [Matrix.blockDiagonal'_apply_ne _ _ _ h]
    exact off_diag T hdec hinv bμ μ₁ μ₂ h i j



end Problems.LinearAlgebra.jordan_normal_form
