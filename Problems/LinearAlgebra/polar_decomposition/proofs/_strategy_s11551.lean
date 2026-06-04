import Mathlib
import Problems.LinearAlgebra.polar_decomposition.Defs
import Problems.LinearAlgebra.polar_decomposition.proofs.L_p_inner_re_eq_sum
import Problems.LinearAlgebra.polar_decomposition.proofs.L_p_sum_sigma_norm_nonneg

namespace Problems.LinearAlgebra.polar_decomposition

-- P : b_E i ↦ σ_i • b_E i is the diagonal operator; show 0 ≤ re ⟪P x, x⟫.
-- Expand the quadratic form on the orthonormal basis (p_inner_re_eq_sum) into the
-- real sum ∑ σ_i ‖⟪b_E i, x⟫‖², then conclude termwise from σ_i ≥ 0
-- (p_sum_sigma_norm_nonneg). Both halves drop the inner-product over a 𝕜-linear map.
theorem s11551 {𝕜 : Type*} [RCLike 𝕜]
  {E : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
  (T : E →ₗ[𝕜] E)
  (b_E : OrthonormalBasis (Fin (Module.finrank 𝕜 E)) 𝕜 E) :
  ∀ x, 0 ≤ RCLike.re (inner 𝕜
    ((b_E.toBasis.constr 𝕜 (fun i => ((T.singularValues i : ℝ) : 𝕜) • b_E i)) x) x)  := by
  intro x
  have h1 := p_inner_re_eq_sum T b_E x
  have h2 := p_sum_sigma_norm_nonneg T b_E x
  rw [h1]; exact h2

end Problems.LinearAlgebra.polar_decomposition
