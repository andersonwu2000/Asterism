import Mathlib
import Problems.LinearAlgebra.eckart_young.Defs

namespace Problems.LinearAlgebra.eckart_young

-- opnorm_ge_of_vector_bound: lifts a pointwise bound c*‖x‖ ≤ ‖A x‖ to the operator norm c ≤ ‖A‖
-- Uses le_opNorm + coe_toContinuousLinearMap' to bridge linear/continuous application,
-- then divides by ‖x‖ > 0 via le_of_mul_le_mul_right.
theorem opnorm_ge_of_vector_bound {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F]
    (A : E →ₗ[𝕜] F) (x : E) (c : ℝ)
    (hx : x ≠ 0) (hbound : c * ‖x‖ ≤ ‖A x‖) :
    c ≤ ‖A.toContinuousLinearMap‖ := by
  have hxpos : 0 < ‖x‖ := norm_pos_iff.mpr hx
  have hle : ‖A x‖ ≤ ‖A.toContinuousLinearMap‖ * ‖x‖ := by
    have h := A.toContinuousLinearMap.le_opNorm x
    simp only [LinearMap.coe_toContinuousLinearMap'] at h
    exact h
  exact le_of_mul_le_mul_right (hbound.trans hle) hxpos


end Problems.LinearAlgebra.eckart_young
