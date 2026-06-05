-- σ₀ ≤ ‖A‖: the top singular value is attained on a unit vector, so it is a lower bound for ‖A‖.
-- Case split on dim E. If dim E = 0 then σ₀ = 0 ≤ ‖A‖ (norm_nonneg). If dim E > 0, sub-goal
-- `exists_unit_vector_norm_eq_singularvalue_zero` produces a unit v with ‖A v‖ = σ₀; then
-- `le_opNorm` gives σ₀ = ‖A v‖ ≤ ‖A‖·‖v‖ = ‖A‖. The sub-goal isolates the eigenvector existence.
import Mathlib
import Problems.LinearAlgebra.eckart_young.Defs
import Problems.LinearAlgebra.eckart_young.proofs._strategy_s11638

namespace Problems.LinearAlgebra.eckart_young

def singularvalue_zero_le_opnorm := @Problems.LinearAlgebra.eckart_young.s11638

end Problems.LinearAlgebra.eckart_young
