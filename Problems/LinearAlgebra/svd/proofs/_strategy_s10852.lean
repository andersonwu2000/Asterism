import Mathlib
import Problems.LinearAlgebra.svd.Defs
import Problems.LinearAlgebra.svd.proofs.L_exists_b_f_with_matrix_diag
import Problems.LinearAlgebra.svd.proofs.L_inner_t_eigenbasis_sq_diag

namespace Problems.LinearAlgebra.svd

-- Decompose into (1) inner products ⟨T(b_E i), T(b_E j)⟩ = σ_i² δ_ij
-- (orthogonality + norm computation from h_eig via ⟨T u, T v⟩ = ⟨u, T†T v⟩
-- and orthonormality of b_E), and (2) construction of b_F with the matrix
-- equation given the inner-product diagonal as a black box. Sub-goal 1 is
-- a pure inner-product algebra step; sub-goal 2 is the construction of u_i
-- via scaling by σ_i⁻¹ and orthonormal completion — strictly simpler than
-- the parent since h_eig is no longer needed once h_inner is established.
theorem s10852 : ∀ {𝕜 : Type*} [RCLike 𝕜]
  {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
  [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
  (T : E →ₗ[𝕜] F)
  (b_E : OrthonormalBasis (Fin (Module.finrank 𝕜 E)) 𝕜 E)
  (h_eig : ∀ i, (T.adjoint ∘ₗ T) (b_E i) =
      (((T.singularValues i : ℝ)^2 : 𝕜)) • b_E i),
  ∃ (b_F : OrthonormalBasis (Fin (Module.finrank 𝕜 F)) 𝕜 F),
    LinearMap.toMatrix b_E.toBasis b_F.toBasis T =
      Matrix.of (fun (j : Fin (Module.finrank 𝕜 F)) (i : Fin (Module.finrank 𝕜 E)) =>
        if (j : ℕ) = (i : ℕ)
        then ((T.singularValues i : ℝ) : 𝕜)
        else 0)  := by
  intro 𝕜 _ E F _ _ _ _ _ _ T b_E h_eig
  have h_inner := inner_t_eigenbasis_sq_diag T b_E h_eig
  exact exists_b_f_with_matrix_diag T b_E h_inner

end Problems.LinearAlgebra.svd
