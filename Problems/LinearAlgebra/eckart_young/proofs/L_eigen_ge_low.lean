import Mathlib
import Problems.LinearAlgebra.eckart_young.Defs

namespace Problems.LinearAlgebra.eckart_young

-- eigen_ge_low: σ_k² ≤ λ_i for i ≤ k, using sq_singularValues_fin + eigenvalues_antitone
theorem eigen_ge_low {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
    (T : E →ₗ[𝕜] F) (k : ℕ) (hk : k < Module.finrank 𝕜 E)
    (i : Fin (Module.finrank 𝕜 E)) (hi : (i : ℕ) ≤ k) :
    (T.singularValues k)^2 ≤ T.isSymmetric_adjoint_comp_self.eigenvalues
      (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E) i := by
  rw [T.sq_singularValues_fin rfl ⟨k, hk⟩]
  exact T.isSymmetric_adjoint_comp_self.eigenvalues_antitone rfl hi

end Problems.LinearAlgebra.eckart_young
