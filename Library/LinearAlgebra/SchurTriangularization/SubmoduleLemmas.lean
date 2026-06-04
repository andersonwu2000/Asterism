import Mathlib

namespace Library.LinearAlgebra.SchurTriangularization.SubmoduleLemmas

-- sup_span_singleton_finrank: rank of U ⊔ span {v} equals rank U + 1 when v ∉ U,
-- via Submodule.finrank_sup_span_singleton from Mathlib.
theorem sup_span_singleton_finrank :
    ∀ {K : Type*} [Field K]
      {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
      (U : Submodule K V) (v : V),
      v ∉ U →
      Module.finrank K ((U ⊔ Submodule.span K {v} : Submodule K V))
        = Module.finrank K U + 1 := by
  intro K _ V _ _ _ U v hv
  exact Submodule.finrank_sup_span_singleton hv

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

-- quotient_nontrivial_of_finrank_lt: finrank gap implies nontrivial quotient via
-- Submodule.finrank_quotient_add_finrank + Module.nontrivial_of_finrank_pos
-- entry_kind: Builder
theorem quotient_nontrivial_of_finrank_lt :
    ∀ {K : Type*} [Field K]
      {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
      (U : Submodule K V),
      Module.finrank K U < Module.finrank K V → Nontrivial (V ⧸ U) := by
  intro K _ V _ _ _ U hlt
  have hU_ne_top : U ≠ ⊤ := by
    intro h
    have : Module.finrank K U = Module.finrank K V := by
      conv_lhs => rw [h]
      exact finrank_top K V
    omega
  have hpos : 0 < Module.finrank K (V ⧸ U) := by
    have := Submodule.finrank_quotient_add_finrank U
    omega
  exact Module.nontrivial_of_finrank_pos hpos

end Library.LinearAlgebra.SchurTriangularization.SubmoduleLemmas
