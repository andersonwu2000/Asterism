import Mathlib
import Problems.LinearAlgebra.svd.Defs

namespace Problems.LinearAlgebra.svd

-- singular_values_zero_high: support_singularValues + Submodule.finrank_le show
-- T.singularValues i = 0 for i ≥ finrank F (support ⊆ Finset.range (finrank T.range))
theorem singular_values_zero_high : ∀ {𝕜 : Type*} [RCLike 𝕜]
  {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
  [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
  (T : E →ₗ[𝕜] F)
  (i : ℕ), Module.finrank 𝕜 F ≤ i → T.singularValues i = 0 := by
  intro 𝕜 _ E F _ _ _ _ _ _ T i hi
  have hsupp : T.singularValues.support = Finset.range (Module.finrank 𝕜 T.range) :=
    LinearMap.support_singularValues T
  have hrange : Module.finrank 𝕜 T.range ≤ Module.finrank 𝕜 F :=
    Submodule.finrank_le T.range
  have hni : i ∉ T.singularValues.support := by
    rw [hsupp]
    simp only [Finset.mem_range, not_lt]
    exact le_trans hrange hi
  simp only [Finsupp.mem_support_iff, ne_eq, not_not] at hni
  exact hni

end Problems.LinearAlgebra.svd
