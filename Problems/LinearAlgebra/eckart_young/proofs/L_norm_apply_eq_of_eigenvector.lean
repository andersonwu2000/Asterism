import Mathlib
import Problems.LinearAlgebra.eckart_young.Defs

namespace Problems.LinearAlgebra.eckart_young

-- norm_apply_eq_of_eigenvector: if v is a unit eigenvector of A†A with eigenvalue s², then ‖Av‖ = s
-- Uses inner_self_eq_norm_sq_to_K + adjoint_inner_left to reduce to an algebraic identity.
theorem norm_apply_eq_of_eigenvector {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
    (A : E →ₗ[𝕜] F) (v : E) (s : ℝ) (hs : 0 ≤ s) (hv : ‖v‖ = 1)
    (heig : (LinearMap.adjoint A ∘ₗ A) v = ((s ^ 2 : ℝ) : 𝕜) • v) :
    ‖A.toContinuousLinearMap v‖ = s := by
  have hAv : ‖(A v : F)‖ ^ 2 = s ^ 2 := by
    rw [norm_sq_eq_re_inner (𝕜 := 𝕜) (A v)]
    rw [← LinearMap.adjoint_inner_left]
    simp only [LinearMap.comp_apply] at heig
    rw [heig, inner_smul_left, RCLike.conj_ofReal, inner_self_eq_norm_sq_to_K, hv]
    simp
  have hclm : ‖A.toContinuousLinearMap v‖ = ‖A v‖ := by
    simp [LinearMap.toContinuousLinearMap]
  rw [hclm]
  have h1 : 0 ≤ ‖A v‖ := norm_nonneg _
  nlinarith [sq_nonneg (‖A v‖ - s), sq_nonneg (‖A v‖ + s)]

end Problems.LinearAlgebra.eckart_young
