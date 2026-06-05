-- Termwise σ_k²‖⟨b_i,x⟩‖² ≤ λ_i‖⟨b_i,x⟩‖²: split on (i:ℕ) ≤ k.
-- Low index (eigen_ge_low): σ_k² = λ_k ≤ λ_i, scale by nonneg ‖⟨b_i,x⟩‖².
-- High index (inner_zero_high): x in top-(k+1) span ⇒ ⟨b_i,x⟩ = 0, both sides vanish.
-- Sub-goals drop the sum/Parseval: a scalar comparison and a coordinate-vanishing fact.
import Mathlib
import Problems.LinearAlgebra.eckart_young.Defs
import Problems.LinearAlgebra.eckart_young.proofs._strategy_s11660

namespace Problems.LinearAlgebra.eckart_young

def eigen_pointwise_lower_bound := @Problems.LinearAlgebra.eckart_young.s11660

end Problems.LinearAlgebra.eckart_young
