import Mathlib
import Problems.LinearAlgebra.svd.Defs

namespace Problems.LinearAlgebra.svd

-- Direct: apply `IsSymmetric.apply_eigenvectorBasis` (eigenvalue scalar form),
-- then identify the eigenvalue with `(T.singularValues i)^2` via `sq_singularValues_fin`.
theorem s10853 : ∀ {𝕜 : Type*} [RCLike 𝕜]
  {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
  [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
  (T : E →ₗ[𝕜] F) (h_sym : (T.adjoint ∘ₗ T).IsSymmetric),
  ∀ i, (T.adjoint ∘ₗ T) (h_sym.eigenvectorBasis rfl i) =
      (((T.singularValues i : ℝ)^2 : 𝕜)) • h_sym.eigenvectorBasis rfl i  := by
  intro 𝕜 _ E F _ _ _ _ _ _ T h_sym i
  rw [h_sym.apply_eigenvectorBasis rfl i]
  congr 1
  have h := T.sq_singularValues_fin (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E) i
  rw [← h]
  push_cast
  ring

end Problems.LinearAlgebra.svd
