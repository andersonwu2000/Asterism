-- Construct the bottom (n−k)-eigenvector subspace W and bound its Rayleigh quotient.
-- bottom_eigenspace_with_support: ∃ W, finrank W = n−k whose vectors have all
--   "high" eigen-modes < k vanishing (⟪eᵢ, x⟫ = 0 for i < k) — the construction half.
-- rayleigh_le_of_low_modes_zero: any x with those modes zero has Rayleigh ≤ λ_k via
--   the eigenbasis expansion + eigenvalue antitonicity — the spectral half, W-free.
-- Combine: pull W from the first, feed its support property into the second pointwise.
import Mathlib
import Problems.LinearAlgebra.courant_fischer.Defs
import Problems.LinearAlgebra.courant_fischer.proofs._strategy_s11622

namespace Problems.LinearAlgebra.courant_fischer

def bottom_eigenspace_exists := @Problems.LinearAlgebra.courant_fischer.s11622

end Problems.LinearAlgebra.courant_fischer
