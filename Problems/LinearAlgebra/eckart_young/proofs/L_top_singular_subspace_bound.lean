-- Eckart–Young, top-(k+1) right-singular subspace.
-- Witness: V = span of the top k+1 eigenvectors of T†T (`isSymmetric_adjoint_comp_self`'s
--   `eigenvectorBasis`, indexed by `Fin.castLE hk` into `Fin (k+1)`).
-- Sub-goal `finrank_span_top_singular_eigenvectors`: dim V = k+1 — the k+1 chosen vectors are
--   distinct members of an orthonormal basis, hence linearly independent, so their span has
--   finrank exactly k+1.
-- Sub-goal `norm_lower_bound_top_singular_span`: ∀ x ∈ V, σ_k‖x‖ ≤ ‖Tx‖ — the SVD spectral
--   content (T maps each top eigenvector to a singular value ≥ σ_k, descending).
-- Combine: exhibit V as the existential witness, pairing the two facts.
import Mathlib
import Problems.LinearAlgebra.eckart_young.Defs
import Problems.LinearAlgebra.eckart_young.proofs._strategy_s11653

namespace Problems.LinearAlgebra.eckart_young

def top_singular_subspace_bound := @Problems.LinearAlgebra.eckart_young.s11653

end Problems.LinearAlgebra.eckart_young
