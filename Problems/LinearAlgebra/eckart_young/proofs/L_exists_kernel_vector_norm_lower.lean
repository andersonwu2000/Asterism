-- Eckart–Young lower bound: a kernel vector of S on which T cannot shrink below σ_k.
-- `exists_top_singular_subspace` builds the (k+1)-dim top right-singular span V on which
-- `σ_k‖x‖ ≤ ‖T x‖` holds (the spectral content). `ker_finrank_ge` gives
-- `finrank E ≤ finrank(ker S) + k` (rank–nullity). Since
-- `finrank V + finrank(ker S) = (k+1) + finrank(ker S) > finrank E`, the 𝕜-version
-- `exists_nonzero_mem_inf_of_finrank` (dimension-count intersection) yields a nonzero
-- `x ∈ V ∩ ker S`; `S x = 0` from `mem_ker`, `σ_k‖x‖ ≤ ‖T x‖` from V's bound.
import Mathlib
import Problems.LinearAlgebra.eckart_young.Defs
import Problems.LinearAlgebra.eckart_young.proofs._strategy_s11647

namespace Problems.LinearAlgebra.eckart_young

def exists_kernel_vector_norm_lower := @Problems.LinearAlgebra.eckart_young.s11647

end Problems.LinearAlgebra.eckart_young
