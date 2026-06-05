-- Eckart–Young lower bound, kernel witness: a nonzero x killed by S with σ_k‖x‖ ≤ ‖T x‖.
-- Sub-goal `top_singular_subspace_bound`: the top-(k+1) right-singular span V (dim k+1)
--   on which T is bounded below by σ_k (the SVD content).
-- Rank–nullity (`finrank_range_add_finrank_ker`) gives dim(ker S) ≥ n−k inline, so
--   dim V + dim(ker S) ≥ (k+1)+(n−k) > n; sub-goal `exists_nonzero_mem_inf_of_finrank`
--   (abstract dimension-counting) yields a nonzero x ∈ V ∩ ker S. Then S x = 0 and the
--   V-bound give the conclusion.
import Mathlib
import Problems.LinearAlgebra.eckart_young.Defs
import Problems.LinearAlgebra.eckart_young.proofs._strategy_s11651

namespace Problems.LinearAlgebra.eckart_young

def kernel_witness_singularvalue := @Problems.LinearAlgebra.eckart_young.s11651

end Problems.LinearAlgebra.eckart_young
