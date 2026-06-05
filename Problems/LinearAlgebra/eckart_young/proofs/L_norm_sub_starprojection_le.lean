import Mathlib
import Problems.LinearAlgebra.eckart_young.Defs

namespace Problems.LinearAlgebra.eckart_young

-- norm_sub_starprojection_le: orthogonal complement contraction — ‖x − Kx‖ ≤ ‖x‖ via Pythagoras
-- Uses orthogonalProjectionFn_norm_sq (Pythagorean identity) to bound the orthogonal residual.
theorem norm_sub_starprojection_le {𝕜 : Type*} [RCLike 𝕜]
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    (K : Submodule 𝕜 E) (x : E) :
    ‖x - K.starProjection x‖ ≤ ‖x‖ := by
  have hpy := K.orthogonalProjectionFn_norm_sq x
  simp only [Submodule.orthogonalProjectionFn_eq, Submodule.coe_orthogonalProjection_apply] at hpy
  nlinarith [norm_nonneg x, norm_nonneg (x - K.starProjection x), norm_nonneg (K.starProjection x)]
end Problems.LinearAlgebra.eckart_young
