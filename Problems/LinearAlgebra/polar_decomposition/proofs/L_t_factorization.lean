-- Direct proof: two linear maps on E agree iff they agree on the basis b_E.
-- `Basis.ext` reduces to a pointwise check; `constr` sends b_E i ↦ σ_i • b_E i,
-- the isometry equiv sends that to σ_i • b_F i (equiv_apply_basis), and h_col
-- gives T (b_E i) = σ_i • b_F i. No sub-goals needed.
import Mathlib
import Problems.LinearAlgebra.polar_decomposition.Defs
import Problems.LinearAlgebra.polar_decomposition.proofs._strategy_s11549

namespace Problems.LinearAlgebra.polar_decomposition

def t_factorization := @Problems.LinearAlgebra.polar_decomposition.s11549

end Problems.LinearAlgebra.polar_decomposition
