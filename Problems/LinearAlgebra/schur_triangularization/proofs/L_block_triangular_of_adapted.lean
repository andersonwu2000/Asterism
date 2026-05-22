import Mathlib
import Problems.LinearAlgebra.schur_triangularization.Defs

namespace Problems.LinearAlgebra.schur_triangularization

-- entry_kind: Builder
-- block_triangular_of_adapted: if T(b j) ∈ span(b '' Set.Iic j) for all j, then the matrix
-- representation of T in basis b is upper-triangular (BlockTriangular id), using repr support.
theorem block_triangular_of_adapted : ∀ {K : Type*} [Field K]
  {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
  (T : V →ₗ[K] V)
  (b : Module.Basis (Fin (Module.finrank K V)) K V),
  (∀ j : Fin (Module.finrank K V),
      T (b j) ∈ Submodule.span K (b '' Set.Iic j)) →
  (LinearMap.toMatrix b b T).BlockTriangular id := by
  intro K _ V _ _ _ T b h i j hij
  rw [LinearMap.toMatrix_apply]
  have hsupp := b.repr_support_subset_of_mem_span (Set.Iic j) (h j)
  have hi : i ∉ Set.Iic j := by simp only [Set.mem_Iic, not_le]; exact hij
  have hi_not_mem : i ∉ (b.repr (T (b j))).support := fun hc => hi (hsupp hc)
  rwa [Finsupp.mem_support_iff, not_not] at hi_not_mem

end Problems.LinearAlgebra.schur_triangularization
