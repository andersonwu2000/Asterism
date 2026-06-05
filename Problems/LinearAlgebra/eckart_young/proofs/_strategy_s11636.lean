import Mathlib
import Problems.LinearAlgebra.eckart_young.Defs
import Problems.LinearAlgebra.eckart_young.proofs.L_opnorm_le_singularvalue_zero
import Problems.LinearAlgebra.eckart_young.proofs.L_singularvalue_zero_le_opnorm

namespace Problems.LinearAlgebra.eckart_young

-- ‖A‖ = σ₀(A) by antisymmetry of two operator-norm bounds.
-- (≤) every vector satisfies ‖A x‖ ≤ σ₀‖x‖ since σ₀² is the top eigenvalue of A†A;
-- (≥) the top right-singular vector achieves ‖A x‖ = σ₀‖x‖, so σ₀ ≤ ‖A‖.
theorem s11636 {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
    (A : E →ₗ[𝕜] F) :
    ‖A.toContinuousLinearMap‖ = A.singularValues 0  := by
  refine le_antisymm ?_ ?_
  · exact opnorm_le_singularvalue_zero A
  · exact singularvalue_zero_le_opnorm A

end Problems.LinearAlgebra.eckart_young
