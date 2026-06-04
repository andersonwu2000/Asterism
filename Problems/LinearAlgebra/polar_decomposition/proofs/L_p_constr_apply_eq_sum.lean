import Mathlib
import Problems.LinearAlgebra.polar_decomposition.Defs

namespace Problems.LinearAlgebra.polar_decomposition

-- entry_kind: Builder
-- p_constr_apply_eq_sum: Basis.constr on orthonormal basis expands via repr_apply_apply
-- (b_E.toBasis.constr 𝕜 f) x = ∑ i, ⟪b_E i, x⟫ • f i; simp fires the constr→repr→inner chain.
theorem p_constr_apply_eq_sum {𝕜 : Type*} [RCLike 𝕜]
  {E : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
  (T : E →ₗ[𝕜] E)
  (b_E : OrthonormalBasis (Fin (Module.finrank 𝕜 E)) 𝕜 E)
  (x : E) :
  (b_E.toBasis.constr 𝕜 (fun i => ((T.singularValues i : ℝ) : 𝕜) • b_E i)) x
      = ∑ i : Fin (Module.finrank 𝕜 E),
          (inner 𝕜 (b_E i) x : 𝕜) • (((T.singularValues (i : ℕ) : ℝ) : 𝕜) • b_E i) := by
  simp [OrthonormalBasis.repr_apply_apply]

end Problems.LinearAlgebra.polar_decomposition
