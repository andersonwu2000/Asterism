import Mathlib
import Problems.LinearAlgebra.polar_decomposition.Defs

namespace Problems.LinearAlgebra.polar_decomposition

-- entry_kind: Builder
theorem re_sum_weighted_eq_real_sum {𝕜 : Type*} [RCLike 𝕜]
  {E : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
  (T : E →ₗ[𝕜] E)
  (b_E : OrthonormalBasis (Fin (Module.finrank 𝕜 E)) 𝕜 E)
  (x : E) :
  RCLike.re (∑ i : Fin (Module.finrank 𝕜 E),
          ((T.singularValues (i : ℕ) : ℝ) : 𝕜) * ((‖(inner 𝕜 (b_E i) x : 𝕜)‖^2 : ℝ) : 𝕜))
      = ∑ i : Fin (Module.finrank 𝕜 E), T.singularValues (i : ℕ) * ‖(inner 𝕜 (b_E i) x : 𝕜)‖^2 := by norm_num

end Problems.LinearAlgebra.polar_decomposition
