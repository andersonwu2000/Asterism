-- Decompose Schur into (1) existence of a basis adapted to T (T(b j) lies in
-- span of earlier basis vectors) and (2) translation of that basis condition
-- to BlockTriangular on the matrix. Sub-goal (1) carries the algebraic-closed
-- induction; sub-goal (2) is a basis-matrix bookkeeping bridge.
import Mathlib
import Problems.LinearAlgebra.schur_triangularization.Defs
import Problems.LinearAlgebra.schur_triangularization.proofs._strategy_s10834

namespace Problems.LinearAlgebra.schur_triangularization

def main := @Problems.LinearAlgebra.schur_triangularization.s10834

end Problems.LinearAlgebra.schur_triangularization
