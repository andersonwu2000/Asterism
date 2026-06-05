-- Spectral half (W-free): expand Rayleigh in the eigenbasis and bound by λ_k.
-- hnum: ⟪Tx,x⟫ = ∑ᵢ λᵢ·(repr x i)²  (own sub-goal; dedupes to sibling).
-- hnorm: ‖x‖² = ∑ᵢ (repr x i)²  (Parseval, leaf).
-- hsum_le: ∑ᵢ λᵢ·(repr x i)² ≤ λ_k·∑ᵢ (repr x i)²  (low modes vanish + antitone).
-- Combine by clearing the positive denominator ‖x‖²>0.
import Mathlib
import Problems.LinearAlgebra.courant_fischer.Defs
import Problems.LinearAlgebra.courant_fischer.proofs._strategy_s11626

namespace Problems.LinearAlgebra.courant_fischer

def rayleigh_le_of_low_modes_zero := @Problems.LinearAlgebra.courant_fischer.s11626

end Problems.LinearAlgebra.courant_fischer
