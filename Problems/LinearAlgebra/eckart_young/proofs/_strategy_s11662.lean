import Mathlib
import Problems.LinearAlgebra.eckart_young.Defs
import Problems.LinearAlgebra.eckart_young.proofs.L_norm_sq_eq_sum_eigen_2
import Problems.LinearAlgebra.eckart_young.proofs.L_termwise_le_singular_k

namespace Problems.LinearAlgebra.eckart_young

-- On `Kᗮ` (K = span of the top-k right singular vectors of `T`), bound `‖T y‖²` by `σ_k² ‖y‖²`.
-- Expand `‖T y‖²` in the eigenbasis of `T†T` (`h_eq`, the diagonalization identity), then bound
-- each summand termwise: `λ_i ‖⟨bᵢ,y⟩‖² ≤ σ_k² ‖⟨bᵢ,y⟩‖²` (`h_term` — vanishes for i<k since
-- y ⊥ K, and `λ_i ≤ σ_k²` for i≥k by antitonicity). Collapse `σ_k² ∑‖⟨bᵢ,y⟩‖² = σ_k² ‖y‖²`
-- via `sum_sq_norm_inner_right` and combine with `Finset.sum_le_sum`.
theorem s11662 {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
    (T : E →ₗ[𝕜] F) (k : ℕ) (hk : k < Module.finrank 𝕜 E) :
    ∀ y ∈ (Submodule.span 𝕜 (Set.range (fun i : Fin k =>
      (T.isSymmetric_adjoint_comp_self.eigenvectorBasis
        (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E)) (Fin.castLE hk.le i))))ᗮ,
      ‖T y‖ ^ 2 ≤ (T.singularValues k) ^ 2 * ‖y‖ ^ 2  := by
  intro y hy
  have h_eq := norm_sq_eq_sum_eigen_2 T y
  rw [h_eq,
      ← (T.isSymmetric_adjoint_comp_self.eigenvectorBasis
        (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E)).sum_sq_norm_inner_right y,
      Finset.mul_sum]
  exact Finset.sum_le_sum (fun i _ => termwise_le_singular_k T k hk y hy i)

end Problems.LinearAlgebra.eckart_young
