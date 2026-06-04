import Mathlib
import Problems.LinearAlgebra.polar_decomposition.Defs

namespace Problems.LinearAlgebra.polar_decomposition

-- entry_kind: Builder
theorem u_isometry : ∀ {𝕜 : Type*} [RCLike 𝕜]
  {E : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
  (b_E b_F : OrthonormalBasis (Fin (Module.finrank 𝕜 E)) 𝕜 E),
  ∀ x, ‖(b_E.equiv b_F (Equiv.refl _)).toLinearMap x‖ = ‖x‖ := by norm_num

end Problems.LinearAlgebra.polar_decomposition
