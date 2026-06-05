-- Spectral lower bound on the top-(k+1) right-singular span: reduce `σ_k‖x‖ ≤ ‖T x‖`
-- to its square `σ_k²‖x‖² ≤ ‖T x‖²` (via `le_of_sq_le_sq`), then diagonalize the Gram
-- operator `T†∘T` in its eigenbasis. Two sub-goals:
--   `re_inner_symm_eq_sum_eigenvalues` — the Rayleigh identity
--     `re⟪Sx,x⟫ = ∑ λ_i ‖⟪b_i,x⟫‖²` for a symmetric `S` (here `S = T†∘T`);
--   `termwise_eigenvalue_bound` — per-coordinate `σ_k²‖⟪b_i,x⟫‖² ≤ λ_i‖⟪b_i,x⟫‖²`
--     (antitone eigenvalues for `i ≤ k`, orthogonality `⟪b_i,x⟫=0` for `i > k`).
-- Summing the termwise bound over the orthonormal eigenbasis (`sum_sq_norm_inner_right`
-- collapses `∑‖⟪b_i,x⟫‖² = ‖x‖²`) yields the squared bound; `‖T x‖² = re⟪T†T x,x⟫`.
import Mathlib
import Problems.LinearAlgebra.eckart_young.Defs
import Problems.LinearAlgebra.eckart_young.proofs._strategy_s11655

namespace Problems.LinearAlgebra.eckart_young

def norm_lower_bound_top_singular_span := @Problems.LinearAlgebra.eckart_young.s11655

end Problems.LinearAlgebra.eckart_young
