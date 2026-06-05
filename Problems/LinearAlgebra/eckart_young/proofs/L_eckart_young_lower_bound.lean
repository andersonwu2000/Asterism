-- Decompose `σ_k ∈ lowerBounds {‖T-S‖ : rank S ≤ k}` into two pieces.
-- After unfolding to `σ_k ≤ ‖T-S‖`, split on `k < finrank E`:
--  • main case: `exists_kernel_vector_norm_lower` gives `x ≠ 0` with `S x = 0`
--    and `σ_k‖x‖ ≤ ‖T x‖`; on `x`, `(T-S) x = T x`, so `opnorm_ge_of_vector_bound`
--    lifts the pointwise bound to the operator norm.
--  • degenerate case `finrank E ≤ k`: `σ_k = 0 ≤ ‖T-S‖`.
import Mathlib
import Problems.LinearAlgebra.eckart_young.Defs
import Problems.LinearAlgebra.eckart_young.proofs._strategy_s11646

namespace Problems.LinearAlgebra.eckart_young

def eckart_young_lower_bound := @Problems.LinearAlgebra.eckart_young.s11646

end Problems.LinearAlgebra.eckart_young
