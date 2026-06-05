import Mathlib
import Problems.LinearAlgebra.eckart_young.Defs
import Problems.LinearAlgebra.eckart_young.proofs.L_eigen_pointwise_lower_bound

namespace Problems.LinearAlgebra.eckart_young

-- σ_k²‖x‖² ≤ ∑ λ_i‖⟨b_i,x⟩‖² for x in the top-(k+1) right-singular span.
-- Parseval (`sum_sq_norm_inner_right`) rewrites ‖x‖² = ∑‖⟨b_i,x⟩‖²; distribute σ_k²
-- into the sum, then compare termwise via the single sub-goal `eigen_pointwise_lower_bound`:
--   σ_k²‖⟨b_i,x⟩‖² ≤ λ_i‖⟨b_i,x⟩‖² (λ_i ≥ σ_k²=λ_k for i≤k; ⟨b_i,x⟩=0 for i>k).
-- Sub-goal is strictly simpler: pointwise, no sum, no Parseval.

theorem s11657 {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
    (T : E →ₗ[𝕜] F) (k : ℕ) (hk : k < Module.finrank 𝕜 E) :
    ∀ x ∈ Submodule.span 𝕜 (Set.range (fun i : Fin (k + 1) =>
      (T.isSymmetric_adjoint_comp_self.eigenvectorBasis
        (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E)) (Fin.castLE hk i))),
      (T.singularValues k)^2 * ‖x‖^2 ≤ ∑ i, (T.isSymmetric_adjoint_comp_self.eigenvalues
        (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E) i)
      * ‖inner 𝕜 ((T.isSymmetric_adjoint_comp_self.eigenvectorBasis
        (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E)) i) x‖^2  := by
  intro x hx
  have hpar : ‖x‖^2 = ∑ i, ‖inner 𝕜 ((T.isSymmetric_adjoint_comp_self.eigenvectorBasis
        (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E)) i) x‖^2 :=
    (OrthonormalBasis.sum_sq_norm_inner_right _ x).symm
  have hpt := eigen_pointwise_lower_bound T k hk x hx
  calc (T.singularValues k)^2 * ‖x‖^2
      = ∑ i, (T.singularValues k)^2 * ‖inner 𝕜
          ((T.isSymmetric_adjoint_comp_self.eigenvectorBasis
            (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E)) i) x‖^2 := by
        rw [hpar, Finset.mul_sum]
    _ ≤ ∑ i, (T.isSymmetric_adjoint_comp_self.eigenvalues
          (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E) i)
        * ‖inner 𝕜 ((T.isSymmetric_adjoint_comp_self.eigenvectorBasis
          (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E)) i) x‖^2 :=
        Finset.sum_le_sum (fun i _ => hpt i)

end Problems.LinearAlgebra.eckart_young
