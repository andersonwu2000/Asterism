import Mathlib
import Problems.LinearAlgebra.eckart_young.Defs
import Problems.LinearAlgebra.eckart_young.proofs.L_eigenvalue_adjoint_self_le_singularvalue_zero_sq
import Problems.LinearAlgebra.eckart_young.proofs.L_re_inner_symm_eq_sum_eigenvalues

namespace Problems.LinearAlgebra.eckart_young

-- Spectral (Rayleigh) bound for the symmetric operator A†A via its eigenbasis.
-- h_rayleigh diagonalizes re⟪A†A x, x⟫ = ∑ μᵢ ‖⟪bᵢ, x⟫‖² over the eigenbasis bᵢ
-- of A†A (μᵢ its eigenvalues); h_eig_le bounds every eigenvalue μᵢ ≤ σ₀².
-- Combine termwise with Finset.sum_le_sum, then collapse ∑ ‖⟪bᵢ, x⟫‖² = ‖x‖²
-- (Parseval, OrthonormalBasis.sum_sq_norm_inner_right). Each sub-goal is a standalone
-- fact (a generic symmetric diagonalization identity; an eigenvalue–singular-value
-- comparison) strictly smaller than the parent Rayleigh inequality.
theorem s11642 {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
    (A : E →ₗ[𝕜] F) (x : E) :
    RCLike.re (inner 𝕜 ((A.adjoint ∘ₗ A) x) x) ≤ (A.singularValues 0) ^ 2 * ‖x‖ ^ 2  := by
  have hn : Module.finrank 𝕜 E = Module.finrank 𝕜 E := rfl
  have h_rayleigh := re_inner_symm_eq_sum_eigenvalues (A.adjoint ∘ₗ A)
    A.isSymmetric_adjoint_comp_self hn x
  have h_eig_le := eigenvalue_adjoint_self_le_singularvalue_zero_sq A hn
  rw [h_rayleigh,
    ← (A.isSymmetric_adjoint_comp_self.eigenvectorBasis hn).sum_sq_norm_inner_right x,
    Finset.mul_sum]
  exact Finset.sum_le_sum fun i _ =>
    mul_le_mul_of_nonneg_right (h_eig_le i) (sq_nonneg _)

end Problems.LinearAlgebra.eckart_young
