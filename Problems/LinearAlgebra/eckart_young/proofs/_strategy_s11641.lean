import Mathlib
import Problems.LinearAlgebra.eckart_young.Defs
import Problems.LinearAlgebra.eckart_young.proofs.L_re_inner_adjoint_le_sv_zero_sq

namespace Problems.LinearAlgebra.eckart_young

-- Reduce ‖A x‖² ≤ σ₀²‖x‖² to the Rayleigh form re⟪A†A x, x⟫ ≤ σ₀²‖x‖².
-- h1: ‖A x‖² = re⟪A†A x, x⟫ is the adjoint identity (adjoint_inner_left + inner_self_eq_norm_sq),
-- proved inline. h2 carries the genuine spectral content (σ₀² bounds the Rayleigh quotient of
-- the symmetric positive A†A). Rewriting by h1 turns the goal into exactly h2.
theorem s11641 {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
    (A : E →ₗ[𝕜] F) (x : E) :
    ‖A x‖ ^ 2 ≤ (A.singularValues 0) ^ 2 * ‖x‖ ^ 2  := by
  have h1 : ‖A x‖ ^ 2 = RCLike.re (inner 𝕜 ((A.adjoint ∘ₗ A) x) x) := by
    rw [LinearMap.comp_apply, LinearMap.adjoint_inner_left, inner_self_eq_norm_sq]
  have h2 := re_inner_adjoint_le_sv_zero_sq A x
  rw [h1]; exact h2

end Problems.LinearAlgebra.eckart_young
