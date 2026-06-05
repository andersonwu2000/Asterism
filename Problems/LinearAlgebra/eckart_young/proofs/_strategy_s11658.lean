import Mathlib
import Problems.LinearAlgebra.eckart_young.Defs
import Problems.LinearAlgebra.eckart_young.proofs.L_inner_eigenvector_high_eq_zero
import Problems.LinearAlgebra.eckart_young.proofs.L_sq_singular_k_le_eigenvalue

namespace Problems.LinearAlgebra.eckart_young

-- Per-coordinate spectral bound `σ_k²‖⟪b_i,x⟫‖² ≤ λ_i‖⟪b_i,x⟫‖²`, split on `i ≤ k`.
-- Case `(i:ℕ) ≤ k`: `σ_k² ≤ λ_i` (`sq_singular_k_le_eigenvalue`, antitone eigenvalues
--   + `sq_singularValues_fin`), then `mul_le_mul_of_nonneg_right` against `‖⟪b_i,x⟫‖² ≥ 0`.
-- Case `k < (i:ℕ)`: `⟪b_i,x⟫ = 0` (`inner_eigenvector_high_eq_zero`, orthogonality of the
--   eigenbasis to the top-(k+1) span containing `x`), so both sides vanish (`simp`).
theorem s11658 {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
    (T : E →ₗ[𝕜] F) (k : ℕ) (hk : k < Module.finrank 𝕜 E)
    (x : E) (hx : x ∈ Submodule.span 𝕜 (Set.range (fun i : Fin (k + 1) =>
      (T.isSymmetric_adjoint_comp_self.eigenvectorBasis
        (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E)) (Fin.castLE hk i))))
    (i : Fin (Module.finrank 𝕜 E)) :
    (T.singularValues k) ^ 2
        * ‖inner 𝕜 (T.isSymmetric_adjoint_comp_self.eigenvectorBasis rfl i) x‖ ^ 2
      ≤ T.isSymmetric_adjoint_comp_self.eigenvalues rfl i
        * ‖inner 𝕜 (T.isSymmetric_adjoint_comp_self.eigenvectorBasis rfl i) x‖ ^ 2  := by
  by_cases hik : (i : ℕ) ≤ k
  · have h_eig := sq_singular_k_le_eigenvalue T k hk i hik
    exact mul_le_mul_of_nonneg_right h_eig (sq_nonneg _)
  · have h_orth := inner_eigenvector_high_eq_zero T k hk x hx i (not_le.mp hik)
    rw [h_orth]; simp

end Problems.LinearAlgebra.eckart_young
