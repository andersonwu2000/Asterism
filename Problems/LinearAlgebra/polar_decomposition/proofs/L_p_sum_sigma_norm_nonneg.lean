import Mathlib
import Problems.LinearAlgebra.polar_decomposition.Defs

namespace Problems.LinearAlgebra.polar_decomposition

-- p_sum_sigma_norm_nonneg: sum of singularValues * ‖inner‖² is nonneg termwise
-- Each term is a product of two nonneg reals: singularValues_nonneg and sq_nonneg of a norm.
-- entry_kind: Builder
theorem p_sum_sigma_norm_nonneg {𝕜 : Type*} [RCLike 𝕜]
  {E : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
  (T : E →ₗ[𝕜] E)
  (b_E : OrthonormalBasis (Fin (Module.finrank 𝕜 E)) 𝕜 E)
  (x : E) :
  0 ≤ ∑ i : Fin (Module.finrank 𝕜 E), T.singularValues (i : ℕ) * ‖(inner 𝕜 (b_E i) x : 𝕜)‖^2 := by
  apply Finset.sum_nonneg
  intro i _
  apply mul_nonneg
  · exact T.singularValues_nonneg i
  · positivity

end Problems.LinearAlgebra.polar_decomposition
