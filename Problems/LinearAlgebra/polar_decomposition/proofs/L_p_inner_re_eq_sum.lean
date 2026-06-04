-- Quadratic form of the diagonal operator P = constr(σ_i • b_E i) on the orthonormal basis b_E.
-- h1: expand P x via constr into ∑ ⟪b_E i, x⟫ • (σ_i • b_E i) (drops the constr abstraction).
-- h2: evaluate ⟪·, x⟫ on that sum; orthonormality collapses it to ∑ σ_i • ‖⟪b_E i, x⟫‖² in 𝕜.
-- h3: push RCLike.re through the sum and the real-scalar products to the final real sum.
import Mathlib
import Problems.LinearAlgebra.polar_decomposition.Defs
import Problems.LinearAlgebra.polar_decomposition.proofs._strategy_s11553

namespace Problems.LinearAlgebra.polar_decomposition

def p_inner_re_eq_sum := @Problems.LinearAlgebra.polar_decomposition.s11553

end Problems.LinearAlgebra.polar_decomposition
