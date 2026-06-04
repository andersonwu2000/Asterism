import Mathlib
import Problems.LinearAlgebra.normal_diagonalization.Defs
import Problems.LinearAlgebra.normal_diagonalization.proofs.L_block_triangular_basis
import Problems.LinearAlgebra.normal_diagonalization.proofs.L_commute_bridge
import Problems.LinearAlgebra.normal_diagonalization.proofs.L_matrix_core

namespace Problems.LinearAlgebra.normal_diagonalization

-- Spectral theorem for normal operators, via the Schur ⇒ spectral route.
-- Decomposition (3 sub-goals + an `obtain`/`exact` combinator):
--   * `block_triangular_basis` — Schur (Library) + Gram-Schmidt give an orthonormal
--     basis `e` in which `T` is (block-)upper-triangular.
--   * `commute_bridge` — normality `Commute (adjoint T) T` transports through the
--     star-algebra equiv to `Commute Mᴴ M` for `M = toMatrix e e T`.
--   * `matrix_core` — pure matrix crux: upper-triangular + normal ⇒ diagonal.
-- They combine: triangularize, then feed triangularity + matrix-normality into the
-- matrix lemma to get `IsDiag`. Each piece is strictly smaller — one basis existence,
-- one star-algebra bridge, one matrix induction.
theorem s11530 : ∀ {V : Type*} [NormedAddCommGroup V] [InnerProductSpace ℂ V]
    [FiniteDimensional ℂ V] (T : V →ₗ[ℂ] V), Commute (LinearMap.adjoint T) T →
    ∃ e : OrthonormalBasis (Fin (Module.finrank ℂ V)) ℂ V,
      (LinearMap.toMatrix e.toBasis e.toBasis T).IsDiag  := by
  intro V _ _ _ T hT
  obtain ⟨e, he⟩ := block_triangular_basis T
  exact ⟨e, matrix_core _ he (commute_bridge T e hT)⟩

end Problems.LinearAlgebra.normal_diagonalization
