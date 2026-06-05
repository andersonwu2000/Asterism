import Mathlib
import Problems.LinearAlgebra.eckart_young.Defs

namespace Problems.LinearAlgebra.eckart_young

-- eigenvalue_adjoint_self_le_singularvalue_zero_sq: every eigenvalue of A†A is ≤ σ₀²
-- Uses sq_singularValues_fin to rewrite eigenvalue as singularValues i², then
-- pow_le_pow_left₀ + singularValues_antitone to bound by singularValues 0².
theorem eigenvalue_adjoint_self_le_singularvalue_zero_sq {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
    (A : E →ₗ[𝕜] F) {n : ℕ} (hn : Module.finrank 𝕜 E = n) (i : Fin n) :
    A.isSymmetric_adjoint_comp_self.eigenvalues hn i ≤ (A.singularValues 0) ^ 2 := by
  rw [← A.sq_singularValues_fin hn i]
  exact pow_le_pow_left₀ (A.singularValues_nonneg _) (A.singularValues_antitone (Nat.zero_le _)) 2

end Problems.LinearAlgebra.eckart_young
