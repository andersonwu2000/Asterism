-- σ_k²‖x‖² ≤ ∑ λ_i‖⟨b_i,x⟩‖² for x in the top-(k+1) right-singular span.
-- Parseval (`sum_sq_norm_inner_right`) rewrites ‖x‖² = ∑‖⟨b_i,x⟩‖²; distribute σ_k²
-- into the sum, then compare termwise via the single sub-goal `eigen_pointwise_lower_bound`:
--   σ_k²‖⟨b_i,x⟩‖² ≤ λ_i‖⟨b_i,x⟩‖² (λ_i ≥ σ_k²=λ_k for i≤k; ⟨b_i,x⟩=0 for i>k).
-- Sub-goal is strictly simpler: pointwise, no sum, no Parseval.
import Mathlib
import Problems.LinearAlgebra.eckart_young.Defs
import Problems.LinearAlgebra.eckart_young.proofs._strategy_s11657

namespace Problems.LinearAlgebra.eckart_young

def sum_eigen_lower_bound := @Problems.LinearAlgebra.eckart_young.s11657

end Problems.LinearAlgebra.eckart_young
