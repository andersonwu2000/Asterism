import Library.LinearAlgebra.NormalDiagonalization.AdaptedBasis
import Library.LinearAlgebra.NormalDiagonalization.MatrixNorm
import Mathlib

/-!
# Spectral theorem for normal operators

This file establishes that every normal operator on a finite-dimensional complex inner product
space is diagonalizable in some orthonormal basis. The proof routes through Schur triangularization
(`block_triangular_basis`) and a matrix-level lemma (`matrix_core`) that promotes
upper-triangularity together with normality to full diagonality.
-/

open Library.LinearAlgebra.NormalDiagonalization.AdaptedBasis
open Library.LinearAlgebra.NormalDiagonalization.MatrixNorm

namespace Library.LinearAlgebra.NormalDiagonalization.Spectral

variable {V : Type*} [NormedAddCommGroup V] [InnerProductSpace ℂ V]
    [FiniteDimensional ℂ V] (T : V →ₗ[ℂ] V)

/-- Given an orthonormal basis `e` and the normality hypothesis `Commute (adjoint T) T`,
transport the commutation relation to the matrix level, yielding
`Commute Mᴴ M` where `M = toMatrix e e T`. -/
theorem commute_bridge
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

/-- Spectral theorem for normal operators: if `T` is a normal operator on a finite-dimensional
complex inner product space, there exists an orthonormal basis in which the matrix of `T` is
diagonal. -/
theorem main (hT : Commute (LinearMap.adjoint T) T) :
    ∃ e : OrthonormalBasis (Fin (Module.finrank ℂ V)) ℂ V,
      (LinearMap.toMatrix e.toBasis e.toBasis T).IsDiag  := by
  obtain ⟨e, he⟩ := block_triangular_basis T
  exact ⟨e, matrix_core _ he (commute_bridge T e hT)⟩

end Library.LinearAlgebra.NormalDiagonalization.Spectral
