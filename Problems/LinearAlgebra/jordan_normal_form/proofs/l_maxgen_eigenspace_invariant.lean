import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs

namespace Problems.LinearAlgebra.jordan_normal_form

-- entry_kind: Builder
-- maxgen_eigenspace_invariant: T maps each maximal generalized eigenspace to itself,
-- via mapsTo_maxGenEigenspace_of_comm with Commute.refl T.
theorem maxgen_eigenspace_invariant
    {K : Type*} [Field K] [DecidableEq K]
    {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
    (T : V →ₗ[K] V) :
    ∀ μ : K, ∀ x ∈ (Module.End.maxGenEigenspace T μ : Submodule K V),
      T x ∈ (Module.End.maxGenEigenspace T μ : Submodule K V) := by
  intro μ x hx
  exact Module.End.mapsTo_maxGenEigenspace_of_comm (Commute.refl T) μ hx

end Problems.LinearAlgebra.jordan_normal_form
