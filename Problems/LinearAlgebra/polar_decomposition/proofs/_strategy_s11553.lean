import Mathlib
import Problems.LinearAlgebra.polar_decomposition.Defs
import Problems.LinearAlgebra.polar_decomposition.proofs.L_inner_diag_sum_eq_weighted
import Problems.LinearAlgebra.polar_decomposition.proofs.L_p_constr_apply_eq_sum
import Problems.LinearAlgebra.polar_decomposition.proofs.L_re_sum_weighted_eq_real_sum

namespace Problems.LinearAlgebra.polar_decomposition

-- Quadratic form of the diagonal operator P = constr(σ_i • b_E i) on the orthonormal basis b_E.
-- h1: expand P x via constr into ∑ ⟪b_E i, x⟫ • (σ_i • b_E i) (drops the constr abstraction).
-- h2: evaluate ⟪·, x⟫ on that sum; orthonormality collapses it to ∑ σ_i • ‖⟪b_E i, x⟫‖² in 𝕜.
-- h3: push RCLike.re through the sum and the real-scalar products to the final real sum.
theorem s11553 {𝕜 : Type*} [RCLike 𝕜]
  {E : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
  (T : E →ₗ[𝕜] E)
  (b_E : OrthonormalBasis (Fin (Module.finrank 𝕜 E)) 𝕜 E)
  (x : E) :
  RCLike.re (inner 𝕜 ((b_E.toBasis.constr 𝕜 (fun i => ((T.singularValues i : ℝ) : 𝕜) • b_E i)) x) x)
    = ∑ i : Fin (Module.finrank 𝕜 E), T.singularValues (i : ℕ) * ‖(inner 𝕜 (b_E i) x : 𝕜)‖^2  := by
  have h1 := p_constr_apply_eq_sum T b_E x
  have h2 := inner_diag_sum_eq_weighted T b_E x
  have h3 := re_sum_weighted_eq_real_sum T b_E x
  rw [h1, h2]; exact h3



end Problems.LinearAlgebra.polar_decomposition
