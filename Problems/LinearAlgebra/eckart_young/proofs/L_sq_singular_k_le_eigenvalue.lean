import Mathlib
import Problems.LinearAlgebra.eckart_young.Defs

namespace Problems.LinearAlgebra.eckart_young

-- sq_singular_k_le_eigenvalue: σ_k² ≤ λ_i for i ≤ k,
-- via antitone singular values + sq_singularValues_fin
theorem sq_singular_k_le_eigenvalue {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
    (T : E →ₗ[𝕜] F) (k : ℕ) (_hk : k < Module.finrank 𝕜 E)
    (i : Fin (Module.finrank 𝕜 E)) (hik : (i : ℕ) ≤ k) :
    T.singularValues k ^ 2
      ≤ T.isSymmetric_adjoint_comp_self.eigenvalues rfl i := by
  calc T.singularValues k ^ 2
      ≤ T.singularValues i ^ 2 := by
        apply pow_le_pow_left₀ (T.singularValues_nonneg k)
        exact T.singularValues_antitone hik
    _ = T.isSymmetric_adjoint_comp_self.eigenvalues rfl i := T.sq_singularValues_fin rfl i

end Problems.LinearAlgebra.eckart_young
