-- Direct proof via `Matrix.fromBlocks` decomposition and `det_fromBlocks₁₁`.
-- Build the equivalence `Fin (m+1) ≃ Fin 1 ⊕ Fin m` (0 ↦ inl 0, succ ↦ inr),
-- express M as the reindexed block matrix, then use the Schur-complement
-- determinant identity; the (D - C * ⅟A * B) block matches the goal's
-- Matrix.of expression after collapsing the 1×1 inverse.
import Mathlib
import Problems.LinearAlgebra.lu_decomposition.Defs
import Problems.LinearAlgebra.lu_decomposition.proofs._strategy_s11329

namespace Problems.LinearAlgebra.lu_decomposition

def schur_det_one_succ := @Problems.LinearAlgebra.lu_decomposition.s11329

end Problems.LinearAlgebra.lu_decomposition
