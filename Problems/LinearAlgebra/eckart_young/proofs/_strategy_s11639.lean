import Mathlib
import Problems.LinearAlgebra.eckart_young.Defs
import Problems.LinearAlgebra.eckart_young.proofs.L_norm_apply_sq_le_singularvalue_zero_sq

namespace Problems.LinearAlgebra.eckart_young

-- Reduce the pointwise bound ‖A x‖ ≤ σ₀‖x‖ to its squared form ‖A x‖² ≤ σ₀²‖x‖²
-- (the genuine spectral content: σ₀² is the top eigenvalue of A†A), then take square
-- roots — both sides are nonnegative (σ₀ ≥ 0, ‖x‖ ≥ 0), so le_of_sq_le_sq closes it.
theorem s11639 {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
    (A : E →ₗ[𝕜] F) (x : E) :
    ‖A x‖ ≤ A.singularValues 0 * ‖x‖  := by
  have h_sq : ‖A x‖ ^ 2 ≤ (A.singularValues 0) ^ 2 * ‖x‖ ^ 2 :=
    norm_apply_sq_le_singularvalue_zero_sq A x
  have hσ : 0 ≤ A.singularValues 0 := A.singularValues_nonneg 0
  have hx : 0 ≤ ‖x‖ := norm_nonneg x
  have key : ‖A x‖ ^ 2 ≤ (A.singularValues 0 * ‖x‖) ^ 2 := by rw [mul_pow]; exact h_sq
  exact le_of_sq_le_sq key (mul_nonneg hσ hx)

end Problems.LinearAlgebra.eckart_young
