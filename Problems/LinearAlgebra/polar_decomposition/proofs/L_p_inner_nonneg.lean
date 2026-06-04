-- P : b_E i ↦ σ_i • b_E i is the diagonal operator; show 0 ≤ re ⟪P x, x⟫.
-- Expand the quadratic form on the orthonormal basis (p_inner_re_eq_sum) into the
-- real sum ∑ σ_i ‖⟪b_E i, x⟫‖², then conclude termwise from σ_i ≥ 0
-- (p_sum_sigma_norm_nonneg). Both halves drop the inner-product over a 𝕜-linear map.
import Mathlib
import Problems.LinearAlgebra.polar_decomposition.Defs
import Problems.LinearAlgebra.polar_decomposition.proofs._strategy_s11551

namespace Problems.LinearAlgebra.polar_decomposition

def p_inner_nonneg := @Problems.LinearAlgebra.polar_decomposition.s11551

end Problems.LinearAlgebra.polar_decomposition
