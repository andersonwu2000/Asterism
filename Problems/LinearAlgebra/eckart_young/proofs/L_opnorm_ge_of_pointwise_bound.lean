import Mathlib
import Problems.LinearAlgebra.eckart_young.Defs

namespace Problems.LinearAlgebra.eckart_young

-- opnorm_ge_of_pointwise_bound: lifts a pointwise bound c*‖y‖ ≤ ‖A y‖ to the operator norm
-- via le_opNorm + coe_toContinuousLinearMap' bridge, then cancels ‖y‖ > 0.
theorem opnorm_ge_of_pointwise_bound {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
    (A : E →ₗ[𝕜] F) (y : E) (c : ℝ) (hy : y ≠ 0) (h : c * ‖y‖ ≤ ‖A y‖) :
    c ≤ ‖A.toContinuousLinearMap‖ := by
  have hle : ‖A y‖ ≤ ‖A.toContinuousLinearMap‖ * ‖y‖ := by
    have := A.toContinuousLinearMap.le_opNorm y
    simp only [LinearMap.coe_toContinuousLinearMap'] at this
    exact this
  exact le_of_mul_le_mul_right (h.trans hle) (norm_pos_iff.mpr hy)

end Problems.LinearAlgebra.eckart_young
