import Mathlib
import Problems.LinearAlgebra.eckart_young.Defs

namespace Problems.LinearAlgebra.eckart_young

-- eig_le_sigma_sq: k-th eigenvalue of T†T is ≤ (σ_k)² using sq_singularValues_fin + antitone
theorem eig_le_sigma_sq {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
    (T : E →ₗ[𝕜] F) (k : ℕ) (hk : k < Module.finrank 𝕜 E)
    (i : Fin (Module.finrank 𝕜 E)) (h : k ≤ (i : ℕ)) :
    T.isSymmetric_adjoint_comp_self.eigenvalues
        (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E) i ≤ (T.singularValues k) ^ 2 := by
  calc T.isSymmetric_adjoint_comp_self.eigenvalues
          (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E) i
      = T.singularValues ↑i ^ 2 := (T.sq_singularValues_fin rfl i).symm
    _ ≤ (T.singularValues k) ^ 2 :=
        pow_le_pow_left₀ (T.singularValues_nonneg ↑i) (T.singularValues_antitone h) 2

end Problems.LinearAlgebra.eckart_young
