import Mathlib
import Problems.LinearAlgebra.schur_triangularization.Defs
import Problems.LinearAlgebra.schur_triangularization.proofs.L_adapted_basis_exists
import Problems.LinearAlgebra.schur_triangularization.proofs.L_block_triangular_of_adapted

namespace Problems.LinearAlgebra.schur_triangularization

-- Decompose Schur into (1) existence of a basis adapted to T (T(b j) lies in
-- span of earlier basis vectors) and (2) translation of that basis condition
-- to BlockTriangular on the matrix. Sub-goal (1) carries the algebraic-closed
-- induction; sub-goal (2) is a basis-matrix bookkeeping bridge.
theorem s10834 : ∀ {K : Type*} [Field K] [IsAlgClosed K]
  {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
  (T : V →ₗ[K] V),
  ∃ b : Module.Basis (Fin (Module.finrank K V)) K V,
    (LinearMap.toMatrix b b T).BlockTriangular id  := by
  intro K _ _ V _ _ _ T
  obtain ⟨b, hb⟩ := adapted_basis_exists T
  exact ⟨b, block_triangular_of_adapted T b hb⟩

end Problems.LinearAlgebra.schur_triangularization
