-- Eckart–Young subspace lower bound: σ_k‖x‖ ≤ ‖Tx‖ on the top-(k+1) right-singular span.
-- Reduce to the squared form via the spectral diagonalization of T†T:
--  (1) `norm_sq_eq_sum_eigen`: ‖Tx‖² = ∑ λ_i ‖⟨b_i,x⟩‖²  (b,λ = eigbasis/eigvals of T†T)
--  (2) `sum_eigen_lower_bound`: σ_k²‖x‖² ≤ ∑ λ_i ‖⟨b_i,x⟩‖²  (subspace + descending eigvals)
-- Combine: σ_k²‖x‖² ≤ ‖Tx‖², rewrite as (σ_k‖x‖)² and take square roots.
import Mathlib
import Problems.LinearAlgebra.eckart_young.Defs
import Problems.LinearAlgebra.eckart_young.proofs._strategy_s11656

namespace Problems.LinearAlgebra.eckart_young

def norm_lower_bound_top_singular_span_2 := @Problems.LinearAlgebra.eckart_young.s11656

end Problems.LinearAlgebra.eckart_young
