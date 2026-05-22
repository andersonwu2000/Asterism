-- Decompose into (1) existence of a T-invariant complete flag — a chain of
-- T-invariant subspaces W_i ≤ V with W_0 = ⊥, monotone, dim W_i = min i n —
-- and (2) extracting an adapted basis from such a flag by picking one
-- representative at each step. Sub-goal (1) carries the alg-closed + induction
-- (eigenvalue extraction, quotient endomorphism). Sub-goal (2) is pure linear
-- algebra (no alg-closed needed): pick a vector in W (i+1) \ W i at each step.
import Mathlib
import Problems.LinearAlgebra.schur_triangularization.Defs
import Problems.LinearAlgebra.schur_triangularization.proofs._strategy_s10835

namespace Problems.LinearAlgebra.schur_triangularization

def adapted_basis_exists := @Problems.LinearAlgebra.schur_triangularization.s10835

end Problems.LinearAlgebra.schur_triangularization
