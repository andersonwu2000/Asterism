-- Spectral diagonalization of the Rayleigh form for a symmetric operator.
-- Expand ⟪T x, x⟫ over the eigenbasis via `sum_inner_mul_inner`; per term use
-- symmetry `⟪T x, bᵢ⟫ = ⟪x, T bᵢ⟫`, `T bᵢ = μᵢ • bᵢ`, and `conj z * z = ‖z‖²`,
-- then `re ∘ ofReal` collapses each real summand. Direct (no sub-goals).
import Mathlib
import Problems.LinearAlgebra.eckart_young.Defs
import Problems.LinearAlgebra.eckart_young.proofs._strategy_s11643

namespace Problems.LinearAlgebra.eckart_young

def re_inner_symm_eq_sum_eigenvalues := @Problems.LinearAlgebra.eckart_young.s11643

end Problems.LinearAlgebra.eckart_young
