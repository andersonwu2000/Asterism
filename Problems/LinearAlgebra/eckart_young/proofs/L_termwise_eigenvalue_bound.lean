-- Per-coordinate spectral bound `σ_k²‖⟪b_i,x⟫‖² ≤ λ_i‖⟪b_i,x⟫‖²`, split on `i ≤ k`.
-- Case `(i:ℕ) ≤ k`: `σ_k² ≤ λ_i` (`sq_singular_k_le_eigenvalue`, antitone eigenvalues
--   + `sq_singularValues_fin`), then `mul_le_mul_of_nonneg_right` against `‖⟪b_i,x⟫‖² ≥ 0`.
-- Case `k < (i:ℕ)`: `⟪b_i,x⟫ = 0` (`inner_eigenvector_high_eq_zero`, orthogonality of the
--   eigenbasis to the top-(k+1) span containing `x`), so both sides vanish (`simp`).
import Mathlib
import Problems.LinearAlgebra.eckart_young.Defs
import Problems.LinearAlgebra.eckart_young.proofs._strategy_s11658

namespace Problems.LinearAlgebra.eckart_young

def termwise_eigenvalue_bound := @Problems.LinearAlgebra.eckart_young.s11658

end Problems.LinearAlgebra.eckart_young
