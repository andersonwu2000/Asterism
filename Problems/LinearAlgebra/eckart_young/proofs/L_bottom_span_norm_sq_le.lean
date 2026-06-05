-- On `Kᗮ` (K = span of the top-k right singular vectors of `T`), bound `‖T y‖²` by `σ_k² ‖y‖²`.
-- Expand `‖T y‖²` in the eigenbasis of `T†T` (`h_eq`, the diagonalization identity), then bound
-- each summand termwise: `λ_i ‖⟨bᵢ,y⟩‖² ≤ σ_k² ‖⟨bᵢ,y⟩‖²` (`h_term` — vanishes for i<k since
-- y ⊥ K, and `λ_i ≤ σ_k²` for i≥k by antitonicity). Collapse `σ_k² ∑‖⟨bᵢ,y⟩‖² = σ_k² ‖y‖²`
-- via `sum_sq_norm_inner_right` and combine with `Finset.sum_le_sum`.
import Mathlib
import Problems.LinearAlgebra.eckart_young.Defs
import Problems.LinearAlgebra.eckart_young.proofs._strategy_s11662

namespace Problems.LinearAlgebra.eckart_young

def bottom_span_norm_sq_le := @Problems.LinearAlgebra.eckart_young.s11662

end Problems.LinearAlgebra.eckart_young
