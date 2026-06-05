-- Termwise weighted-sum bound: distribute λ_k over the sum, then compare term by term.
-- Each term λ_k·rᵢ² ≤ λᵢ·rᵢ²: for i ≤ k the antitone (decreasing) spectrum gives λ_k ≤ λᵢ
-- and rᵢ² ≥ 0; for k < i the high mode vanishes (hv), making both sides 0.
-- Direct (sorry-free) leaf proof: Finset.mul_sum + Finset.sum_le_sum, no sub-goals.
import Mathlib
import Problems.LinearAlgebra.courant_fischer.Defs
import Problems.LinearAlgebra.courant_fischer.proofs._strategy_s11635

namespace Problems.LinearAlgebra.courant_fischer

def weighted_eigenvalue_sum_ge := @Problems.LinearAlgebra.courant_fischer.s11635

end Problems.LinearAlgebra.courant_fischer
