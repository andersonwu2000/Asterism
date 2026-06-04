-- Transport operator normality to matrix normality via the star-algebra equiv.
-- `toMatrix_adjoint` rewrites `Mᴴ = toMatrix e e (adjoint T)`, then `Commute.map`
-- through the star-algebra equiv `toMatrixOrthonormal e` carries `Commute (adjoint T) T`
-- to the matrix `Commute`. Direct cite — no sub-goals.
import Mathlib
import Problems.LinearAlgebra.normal_diagonalization.Defs
import Problems.LinearAlgebra.normal_diagonalization.proofs._strategy_s11543

namespace Problems.LinearAlgebra.normal_diagonalization

def commute_bridge := @Problems.LinearAlgebra.normal_diagonalization.s11543

end Problems.LinearAlgebra.normal_diagonalization
