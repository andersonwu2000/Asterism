-- Lower bound: σ_k ≤ ‖T−S‖ for every rank-≤k S. Unfold the lowerBounds set,
-- split on whether k indexes a real singular value.
-- Sub-goal `kernel_witness_singularvalue`: rank-nullity + top-(k+1) right-singular
-- span ∩ ker S yields a nonzero x with S x = 0 and σ_k‖x‖ ≤ ‖T x‖.
-- Sub-goal `opnorm_ge_of_pointwise_bound`: a pointwise lower bound on a unit-direction
-- lifts to the operator norm. Degenerate branch (finrank E ≤ k): σ_k = 0 ≤ ‖·‖.
import Mathlib
import Problems.LinearAlgebra.eckart_young.Defs
import Problems.LinearAlgebra.eckart_young.proofs._strategy_s11649

namespace Problems.LinearAlgebra.eckart_young

def singularvalue_mem_lowerbounds := @Problems.LinearAlgebra.eckart_young.s11649

end Problems.LinearAlgebra.eckart_young
