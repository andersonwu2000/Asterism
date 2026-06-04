import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs

namespace Problems.LinearAlgebra.jordan_normal_form

theorem jordan_form_assembly_from_decomposition
    {K : Type*} [Field K] [DecidableEq K]
    {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
    (T : V →ₗ[K] V)
    (hdec : DirectSum.IsInternal
      (fun μ : K => (Module.End.maxGenEigenspace T μ : Submodule K V)))
    (hJordNilp : ∀ μ : K,
        ∀ (N : (Module.End.maxGenEigenspace T μ : Submodule K V) →ₗ[K]
                (Module.End.maxGenEigenspace T μ : Submodule K V)),
          IsNilpotent N →
          ∃ b : Module.Basis
                  (Fin (Module.finrank K (Module.End.maxGenEigenspace T μ : Submodule K V)))
                  K (Module.End.maxGenEigenspace T μ : Submodule K V),
            IsJordanForm (LinearMap.toMatrix b b N) ∧
            ∀ i, (LinearMap.toMatrix b b N) i i = 0) :
    ∃ b : Module.Basis (Fin (Module.finrank K V)) K V,
      IsJordanForm (LinearMap.toMatrix b b T) := by
  sorry

end Problems.LinearAlgebra.jordan_normal_form
