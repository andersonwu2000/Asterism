-- Rayleigh numerator bound: expand both sides in the orthonormal eigenbasis.
-- (1) ⟪Tx,x⟫ = ∑ λᵢ·(repr x i)²  (numerator_eigenbasis_expand);
-- (2) ‖x‖² = ∑ (repr x i)²        (norm_sq_eq_sum_repr_sq);
-- (3) with the high modes (i>k) vanishing, antitone spectrum gives the
--     termwise/summed bound λ_k·∑(repr)² ≤ ∑ λᵢ·(repr)² (weighted_eigenvalue_sum_ge).
-- Rewrite by (1),(2) and close with (3).
import Mathlib
import Problems.LinearAlgebra.courant_fischer.Defs
import Problems.LinearAlgebra.courant_fischer.proofs._strategy_s11632

namespace Problems.LinearAlgebra.courant_fischer

def numerator_ge_eigenvalue := @Problems.LinearAlgebra.courant_fischer.s11632

end Problems.LinearAlgebra.courant_fischer
