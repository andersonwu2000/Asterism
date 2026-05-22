import Mathlib
import Problems.LinearAlgebra.schur_triangularization.Defs

namespace Problems.LinearAlgebra.schur_triangularization

-- sup_span_singleton_invariant: T-invariance of U ⊔ span{v} via Submodule.mem_sup decomposition
-- Decompose w = u + c•v; T w = (Tu + c•(Tv−μ•v)) + (c*μ)•v, first part in U, second in span{v}.
-- entry_kind: Builder
theorem sup_span_singleton_invariant :
    ∀ {K : Type*} [Field K]
      {V : Type*} [AddCommGroup V] [Module K V]
      (T : V →ₗ[K] V) (U : Submodule K V) (v : V) (μ : K),
      (∀ w ∈ U, T w ∈ U) →
      T v - μ • v ∈ U →
      ∀ w ∈ U ⊔ Submodule.span K {v}, T w ∈ U ⊔ Submodule.span K {v} := by
  intro K _ V _ _ T U v μ hTU hTv w hw
  obtain ⟨u, hu, s, hs, rfl⟩ := Submodule.mem_sup.mp hw
  obtain ⟨c, rfl⟩ := Submodule.mem_span_singleton.mp hs
  simp only [map_add, map_smul]
  apply Submodule.mem_sup.mpr
  refine ⟨T u + c • (T v - μ • v), U.add_mem (hTU u hu) (U.smul_mem c hTv),
          (c * μ) • v, Submodule.mem_span_singleton.mpr ⟨c * μ, rfl⟩, ?_⟩
  simp only [smul_sub, smul_smul]
  abel
end Problems.LinearAlgebra.schur_triangularization
