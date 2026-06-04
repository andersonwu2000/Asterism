import Mathlib
import Problems.LinearAlgebra.polar_decomposition.Defs
import Problems.LinearAlgebra.polar_decomposition.proofs.L_p_inner_nonneg
import Problems.LinearAlgebra.polar_decomposition.proofs.L_p_symmetric

namespace Problems.LinearAlgebra.polar_decomposition

-- Decompose `P.IsPositive` for the diagonal operator P : b_E i ↦ σ_i • b_E i.
-- `LinearMap.IsPositive` unfolds to `IsSymmetric P ∧ ∀ x, 0 ≤ re ⟪P x, x⟫`; split into
-- the two independent halves and recombine with the anonymous constructor ⟨·, ·⟩.
-- Both sub-goals are strictly simpler than positivity:
--  • p_symmetric: ⟪P x, y⟫ = ⟪x, P y⟫ — the diagonal entries σ_i are real, so P is
--    self-adjoint; reduces to a basis-coordinate computation.
--  • p_inner_nonneg: 0 ≤ re ⟪P x, x⟫ — expands to ∑ σ_i ‖⟪x, b_E i⟫‖² ≥ 0 using
--    σ_i ≥ 0 (LinearMap.singularValues_nonneg).
theorem s11550 : ∀ {𝕜 : Type*} [RCLike 𝕜]
  {E : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
  (T : E →ₗ[𝕜] E)
  (b_E : OrthonormalBasis (Fin (Module.finrank 𝕜 E)) 𝕜 E),
  (b_E.toBasis.constr 𝕜 (fun i => ((T.singularValues i : ℝ) : 𝕜) • b_E i)).IsPositive  := by
  intro 𝕜 _ E _ _ _ T b_E
  have h_sym := p_symmetric T b_E
  have h_nonneg := p_inner_nonneg T b_E
  exact ⟨h_sym, h_nonneg⟩

end Problems.LinearAlgebra.polar_decomposition
