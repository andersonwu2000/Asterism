import Mathlib
import Problems.LinearAlgebra.normal_diagonalization.Defs

namespace Problems.LinearAlgebra.normal_diagonalization

-- Transport operator normality to matrix normality via the star-algebra equiv.
-- `toMatrix_adjoint` rewrites `Mᴴ = toMatrix e e (adjoint T)`, then `Commute.map`
-- through the star-algebra equiv `toMatrixOrthonormal e` carries `Commute (adjoint T) T`
-- to the matrix `Commute`. Direct cite — no sub-goals.
theorem s11543 {V : Type*} [NormedAddCommGroup V] [InnerProductSpace ℂ V]
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

end Problems.LinearAlgebra.normal_diagonalization
