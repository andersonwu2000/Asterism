import Library.LinearAlgebra.SchurTriangularization.FlagBasis
import Library.LinearAlgebra.SchurTriangularization.InvariantFlag
import Mathlib

open Library.LinearAlgebra.SchurTriangularization.FlagBasis
open Library.LinearAlgebra.SchurTriangularization.InvariantFlag

namespace Library.LinearAlgebra.SchurTriangularization.Triangularization

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

-- Decompose into (1) existence of a T-invariant complete flag — a chain of
-- T-invariant subspaces W_i ≤ V with W_0 = ⊥, monotone, dim W_i = min i n —
-- and (2) extracting an adapted basis from such a flag by picking one
-- representative at each step. Sub-goal (1) carries the alg-closed + induction
-- (eigenvalue extraction, quotient endomorphism). Sub-goal (2) is pure linear
-- algebra (no alg-closed needed): pick a vector in W (i+1) \ W i at each step.
theorem adapted_basis_exists : ∀ {K : Type*} [Field K] [IsAlgClosed K]
  {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
  (T : V →ₗ[K] V),
  ∃ b : Module.Basis (Fin (Module.finrank K V)) K V,
    ∀ j : Fin (Module.finrank K V),
      T (b j) ∈ Submodule.span K (b '' Set.Iic j)  := by
  intro K _ _ V _ _ _ T
  obtain ⟨W, hW0, hWmono, hWdim, hWinv⟩ := invariant_flag_exists T
  exact adapted_basis_of_flag T W hW0 hWmono hWdim hWinv

-- Decompose Schur into (1) existence of a basis adapted to T (T(b j) lies in
-- span of earlier basis vectors) and (2) translation of that basis condition
-- to BlockTriangular on the matrix. Sub-goal (1) carries the algebraic-closed
-- induction; sub-goal (2) is a basis-matrix bookkeeping bridge.
theorem main : ∀ {K : Type*} [Field K] [IsAlgClosed K]
  {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
  (T : V →ₗ[K] V),
  ∃ b : Module.Basis (Fin (Module.finrank K V)) K V,
    (LinearMap.toMatrix b b T).BlockTriangular id  := by
  intro K _ _ V _ _ _ T
  obtain ⟨b, hb⟩ := adapted_basis_exists T
  exact ⟨b, block_triangular_of_adapted T b hb⟩

end Library.LinearAlgebra.SchurTriangularization.Triangularization
