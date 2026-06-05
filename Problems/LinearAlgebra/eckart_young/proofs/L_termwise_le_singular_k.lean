-- Termwise bound `λ_i ‖⟨bᵢ,y⟩‖² ≤ σ_k² ‖⟨bᵢ,y⟩‖²` on `Kᗮ`, by case on `i` vs `k`.
-- `i ≥ k`: `λ_i ≤ σ_k²` by antitonicity (`eig_le_sigma_sq`), scaled by `‖⟨bᵢ,y⟩‖² ≥ 0`.
-- `i < k`: `bᵢ ∈ K` so `⟨bᵢ,y⟩ = 0` (`inner_eigvec_orthogonal`); both sides vanish.
import Mathlib
import Problems.LinearAlgebra.eckart_young.Defs
import Problems.LinearAlgebra.eckart_young.proofs._strategy_s11664

namespace Problems.LinearAlgebra.eckart_young

def termwise_le_singular_k := @Problems.LinearAlgebra.eckart_young.s11664

end Problems.LinearAlgebra.eckart_young
