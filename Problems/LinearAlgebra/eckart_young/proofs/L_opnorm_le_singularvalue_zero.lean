-- ‖A‖ ≤ σ₀ via the pointwise operator bound ‖A x‖ ≤ σ₀ ‖x‖.
-- ContinuousLinearMap.opNorm_le_bound reduces ‖A‖ ≤ σ₀ to nonnegativity of σ₀
-- (LinearMap.singularValues_nonneg) plus the single pointwise bound sub-goal,
-- which carries the spectral content (σ₀² = top eigenvalue of A†A).
import Mathlib
import Problems.LinearAlgebra.eckart_young.Defs
import Problems.LinearAlgebra.eckart_young.proofs._strategy_s11637

namespace Problems.LinearAlgebra.eckart_young

def opnorm_le_singularvalue_zero := @Problems.LinearAlgebra.eckart_young.s11637

end Problems.LinearAlgebra.eckart_young
