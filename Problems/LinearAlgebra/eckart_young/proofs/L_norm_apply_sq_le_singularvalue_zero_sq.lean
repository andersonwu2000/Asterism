-- Reduce ‖A x‖² ≤ σ₀²‖x‖² to the Rayleigh form re⟪A†A x, x⟫ ≤ σ₀²‖x‖².
-- h1: ‖A x‖² = re⟪A†A x, x⟫ is the adjoint identity (adjoint_inner_left + inner_self_eq_norm_sq),
-- proved inline. h2 carries the genuine spectral content (σ₀² bounds the Rayleigh quotient of
-- the symmetric positive A†A). Rewriting by h1 turns the goal into exactly h2.
import Mathlib
import Problems.LinearAlgebra.eckart_young.Defs
import Problems.LinearAlgebra.eckart_young.proofs._strategy_s11641

namespace Problems.LinearAlgebra.eckart_young

def norm_apply_sq_le_singularvalue_zero_sq := @Problems.LinearAlgebra.eckart_young.s11641

end Problems.LinearAlgebra.eckart_young
