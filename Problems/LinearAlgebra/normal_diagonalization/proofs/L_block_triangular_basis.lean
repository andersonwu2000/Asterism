-- Triangularization in an orthonormal basis = (Schur ⇒ adapted ordinary basis,
-- then Gram-Schmidt to an orthonormal one preserving the flag) + the Library
-- bookkeeping lemma `block_triangular_of_adapted`.
-- Sub-goal `adapted_orthonormal_basis` packages Schur+Gram-Schmidt into the
-- existence of an orthonormal basis `e` with the adapted (flag) condition; the
-- Library lemma then turns that condition into `BlockTriangular id`. The single
-- sub-goal is strictly simpler: it drops all matrix-entry bookkeeping.
import Mathlib
import Problems.LinearAlgebra.normal_diagonalization.Defs
import Problems.LinearAlgebra.normal_diagonalization.proofs._strategy_s11531

namespace Problems.LinearAlgebra.normal_diagonalization

def block_triangular_basis := @Problems.LinearAlgebra.normal_diagonalization.s11531

end Problems.LinearAlgebra.normal_diagonalization
