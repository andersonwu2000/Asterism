-- Spectral (Rayleigh) bound for the symmetric operator A†A via its eigenbasis.
-- h_rayleigh diagonalizes re⟪A†A x, x⟫ = ∑ μᵢ ‖⟪bᵢ, x⟫‖² over the eigenbasis bᵢ
-- of A†A (μᵢ its eigenvalues); h_eig_le bounds every eigenvalue μᵢ ≤ σ₀².
-- Combine termwise with Finset.sum_le_sum, then collapse ∑ ‖⟪bᵢ, x⟫‖² = ‖x‖²
-- (Parseval, OrthonormalBasis.sum_sq_norm_inner_right). Each sub-goal is a standalone
-- fact (a generic symmetric diagonalization identity; an eigenvalue–singular-value
-- comparison) strictly smaller than the parent Rayleigh inequality.
import Mathlib
import Problems.LinearAlgebra.eckart_young.Defs
import Problems.LinearAlgebra.eckart_young.proofs._strategy_s11642

namespace Problems.LinearAlgebra.eckart_young

def re_inner_adjoint_le_sv_zero_sq := @Problems.LinearAlgebra.eckart_young.s11642

end Problems.LinearAlgebra.eckart_young
