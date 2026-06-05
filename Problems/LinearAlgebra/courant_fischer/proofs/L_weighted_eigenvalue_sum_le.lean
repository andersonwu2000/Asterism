-- Term-wise bound: ∑ λᵢ·(repr x i)² ≤ λ_k·∑ (repr x i)², via `Finset.sum_le_sum`.
-- For i < k the coefficient `repr x i = ⟪eᵢ, x⟫ = 0` (hzero) kills both sides;
-- for k ≤ i, `eigenvalues_antitone` gives λᵢ ≤ λ_k and `(repr x i)² ≥ 0` lifts it.
-- Direct leaf — no sub-goals.
import Mathlib
import Problems.LinearAlgebra.courant_fischer.Defs
import Problems.LinearAlgebra.courant_fischer.proofs._strategy_s11634

namespace Problems.LinearAlgebra.courant_fischer

def weighted_eigenvalue_sum_le := @Problems.LinearAlgebra.courant_fischer.s11634

end Problems.LinearAlgebra.courant_fischer
