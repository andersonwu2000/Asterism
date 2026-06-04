import Mathlib
import Problems.LinearAlgebra.normal_diagonalization.Defs
import Library.LinearAlgebra.SchurTriangularization.Triangularization
import Problems.LinearAlgebra.normal_diagonalization.proofs.L_adapted_orthonormal_basis

namespace Problems.LinearAlgebra.normal_diagonalization

open Library.LinearAlgebra.SchurTriangularization.Triangularization

-- Triangularization in an orthonormal basis = (Schur ⇒ adapted ordinary basis,
-- then Gram-Schmidt to an orthonormal one preserving the flag) + the Library
-- bookkeeping lemma `block_triangular_of_adapted`.
-- Sub-goal `adapted_orthonormal_basis` packages Schur+Gram-Schmidt into the
-- existence of an orthonormal basis `e` with the adapted (flag) condition; the
-- Library lemma then turns that condition into `BlockTriangular id`. The single
-- sub-goal is strictly simpler: it drops all matrix-entry bookkeeping.
theorem s11531 {V : Type*} [NormedAddCommGroup V] [InnerProductSpace ℂ V]
    [FiniteDimensional ℂ V] (T : V →ₗ[ℂ] V) :
    ∃ e : OrthonormalBasis (Fin (Module.finrank ℂ V)) ℂ V,
      (LinearMap.toMatrix e.toBasis e.toBasis T).BlockTriangular id  := by
  obtain ⟨e, he⟩ := adapted_orthonormal_basis T
  exact ⟨e, block_triangular_of_adapted T e.toBasis he⟩

end Problems.LinearAlgebra.normal_diagonalization
