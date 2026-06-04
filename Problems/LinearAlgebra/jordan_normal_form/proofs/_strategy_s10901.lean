import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs

namespace Problems.LinearAlgebra.jordan_normal_form

theorem s10901
    {K : Type*} [Field K]
    {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
    (T : V →ₗ[K] V)
    (hinv : ∀ μ : K, ∀ x ∈ (Module.End.maxGenEigenspace T μ : Submodule K V),
        T x ∈ (Module.End.maxGenEigenspace T μ : Submodule K V))
    (μ : K) :
    IsNilpotent (T.restrict (hinv μ)
        - μ • (1 : Module.End K (Module.End.maxGenEigenspace T μ : Submodule K V)))  := by
  have hmaps : Set.MapsTo ⇑(T - algebraMap K (Module.End K V) μ)
      (Module.End.maxGenEigenspace T μ : Submodule K V)
      (Module.End.maxGenEigenspace T μ : Submodule K V) := by
    intro x hx
    simp only [LinearMap.sub_apply, Algebra.algebraMap_eq_smul_one,
      LinearMap.smul_apply, Module.End.one_apply, SetLike.mem_coe]
    exact Submodule.sub_mem _ (hinv μ x hx) (Submodule.smul_mem _ _ hx)
  have key := Module.End.isNilpotent_restrict_maxGenEigenspace_sub_algebraMap T μ hmaps
  have heq : T.restrict (hinv μ)
      - μ • (1 : Module.End K (Module.End.maxGenEigenspace T μ : Submodule K V))
      = (T - algebraMap K (Module.End K V) μ).restrict hmaps := by
    ext x
    simp [LinearMap.restrict_apply, LinearMap.sub_apply, Algebra.algebraMap_eq_smul_one]
  rw [heq]; exact key

end Problems.LinearAlgebra.jordan_normal_form
