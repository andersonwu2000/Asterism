import Mathlib
import Problems.LinearAlgebra.eckart_young.Defs
import Problems.LinearAlgebra.eckart_young.proofs.L_norm_apply_le_singularvalue_zero

namespace Problems.LinearAlgebra.eckart_young

-- ‖A‖ ≤ σ₀ via the pointwise operator bound ‖A x‖ ≤ σ₀ ‖x‖.
-- ContinuousLinearMap.opNorm_le_bound reduces ‖A‖ ≤ σ₀ to nonnegativity of σ₀
-- (LinearMap.singularValues_nonneg) plus the single pointwise bound sub-goal,
-- which carries the spectral content (σ₀² = top eigenvalue of A†A).
theorem s11637 {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
    (A : E →ₗ[𝕜] F) :
    ‖A.toContinuousLinearMap‖ ≤ A.singularValues 0  := by
  apply ContinuousLinearMap.opNorm_le_bound _ (A.singularValues_nonneg 0)
  intro x
  have h_bound : ‖A x‖ ≤ A.singularValues 0 * ‖x‖ := norm_apply_le_singularvalue_zero A x
  simpa using h_bound

end Problems.LinearAlgebra.eckart_young
