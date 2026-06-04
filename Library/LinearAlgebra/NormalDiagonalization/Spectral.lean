import Library.LinearAlgebra.NormalDiagonalization.AdaptedBasis
import Library.LinearAlgebra.NormalDiagonalization.MatrixNorm
import Mathlib

open Library.LinearAlgebra.NormalDiagonalization.AdaptedBasis
open Library.LinearAlgebra.NormalDiagonalization.MatrixNorm

namespace Library.LinearAlgebra.NormalDiagonalization.Spectral

-- Transport operator normality to matrix normality via the star-algebra equiv.
-- `toMatrix_adjoint` rewrites `Mᴴ = toMatrix e e (adjoint T)`, then `Commute.map`
-- through the star-algebra equiv `toMatrixOrthonormal e` carries `Commute (adjoint T) T`
-- to the matrix `Commute`. Direct cite — no sub-goals.
theorem commute_bridge {V : Type*} [NormedAddCommGroup V] [InnerProductSpace ℂ V]
    [FiniteDimensional ℂ V] (T : V →ₗ[ℂ] V)
    (e : OrthonormalBasis (Fin (Module.finrank ℂ V)) ℂ V)
    (hT : Commute (LinearMap.adjoint T) T) :
    Commute (Matrix.conjTranspose (LinearMap.toMatrix e.toBasis e.toBasis T))
      (LinearMap.toMatrix e.toBasis e.toBasis T)  := by
  have hadj : Matrix.conjTranspose (LinearMap.toMatrix e.toBasis e.toBasis T)
      = LinearMap.toMatrix e.toBasis e.toBasis (LinearMap.adjoint T) :=
    (LinearMap.toMatrix_adjoint e e T).symm
  rw [hadj]
  have h := hT.map (LinearMap.toMatrixOrthonormal e)
  simpa [LinearMap.toMatrixOrthonormal] using h

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
theorem main : ∀ {V : Type*} [NormedAddCommGroup V] [InnerProductSpace ℂ V]
    [FiniteDimensional ℂ V] (T : V →ₗ[ℂ] V), Commute (LinearMap.adjoint T) T →
    ∃ e : OrthonormalBasis (Fin (Module.finrank ℂ V)) ℂ V,
      (LinearMap.toMatrix e.toBasis e.toBasis T).IsDiag  := by
  intro V _ _ _ T hT
  obtain ⟨e, he⟩ := block_triangular_basis T
  exact ⟨e, matrix_core _ he (commute_bridge T e hT)⟩

end Library.LinearAlgebra.NormalDiagonalization.Spectral
