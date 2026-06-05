import Mathlib
import Problems.LinearAlgebra.eckart_young.Defs
import Problems.LinearAlgebra.eckart_young.proofs.L_eig_le_sigma_sq
import Problems.LinearAlgebra.eckart_young.proofs.L_inner_eigvec_orthogonal

namespace Problems.LinearAlgebra.eckart_young

-- Termwise bound `λ_i ‖⟨bᵢ,y⟩‖² ≤ σ_k² ‖⟨bᵢ,y⟩‖²` on `Kᗮ`, by case on `i` vs `k`.
-- `i ≥ k`: `λ_i ≤ σ_k²` by antitonicity (`eig_le_sigma_sq`), scaled by `‖⟨bᵢ,y⟩‖² ≥ 0`.
-- `i < k`: `bᵢ ∈ K` so `⟨bᵢ,y⟩ = 0` (`inner_eigvec_orthogonal`); both sides vanish.
theorem s11664 {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
    (T : E →ₗ[𝕜] F) (k : ℕ) (hk : k < Module.finrank 𝕜 E)
    (y : E) (hy : y ∈ (Submodule.span 𝕜 (Set.range (fun i : Fin k =>
      (T.isSymmetric_adjoint_comp_self.eigenvectorBasis
        (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E)) (Fin.castLE hk.le i))))ᗮ)
    (i : Fin (Module.finrank 𝕜 E)) :
    T.isSymmetric_adjoint_comp_self.eigenvalues
        (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E) i
        * ‖inner 𝕜 ((T.isSymmetric_adjoint_comp_self.eigenvectorBasis
            (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E)) i) y‖ ^ 2
      ≤ (T.singularValues k) ^ 2
        * ‖inner 𝕜 ((T.isSymmetric_adjoint_comp_self.eigenvectorBasis
            (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E)) i) y‖ ^ 2  := by
  by_cases h : k ≤ (i : ℕ)
  · have h_eig := eig_le_sigma_sq T k hk i h
    exact mul_le_mul_of_nonneg_right h_eig (sq_nonneg _)
  · have h_orth := inner_eigvec_orthogonal T k hk y hy i (not_le.mp h)
    rw [h_orth]
    simp

end Problems.LinearAlgebra.eckart_young
