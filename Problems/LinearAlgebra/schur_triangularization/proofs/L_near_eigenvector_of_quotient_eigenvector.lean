import Mathlib
import Problems.LinearAlgebra.schur_triangularization.Defs

namespace Problems.LinearAlgebra.schur_triangularization

-- entry_kind: Builder
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

end Problems.LinearAlgebra.schur_triangularization