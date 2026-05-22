import Mathlib
import Problems.LinearAlgebra.svd.Defs

namespace Problems.LinearAlgebra.svd

-- t_adjoint_t_is_symmetric: T†∘T is symmetric via adjoint_inner_left/right chain
-- entry_kind: Builder
theorem t_adjoint_t_is_symmetric : ∀ {𝕜 : Type*} [RCLike 𝕜]
  {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
  [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
  (T : E →ₗ[𝕜] F),
  (T.adjoint ∘ₗ T).IsSymmetric := by
  intro 𝕜 _ E F _ _ _ _ _ _ T x y
  simp [LinearMap.comp_apply, LinearMap.adjoint_inner_left, LinearMap.adjoint_inner_right]

end Problems.LinearAlgebra.svd
