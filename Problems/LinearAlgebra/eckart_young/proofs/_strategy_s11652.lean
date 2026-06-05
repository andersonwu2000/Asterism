import Mathlib
import Problems.LinearAlgebra.eckart_young.Defs
import Problems.LinearAlgebra.eckart_young.proofs.L_exists_truncation_projection

namespace Problems.LinearAlgebra.eckart_young

-- Membership direction of Eckart–Young: build a rank-≤k truncation `S` whose
-- residual is pointwise bounded by σ_k.  Factor `S = T ∘ₗ P` through a rank-≤k
-- projection `P : E →ₗ E` (sub-goal `exists_truncation_projection`, the SVD/
-- spectral content).  Then `range (T∘ₗP) = T.map (range P)` has finrank ≤
-- finrank (range P) ≤ k (`Submodule.finrank_map_le`), and `(T-S) x = T x - T(Px)`
-- (`LinearMap.sub_apply`/`comp_apply`) inherits the pointwise bound directly.

theorem s11652 {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
    (T : E →ₗ[𝕜] F) (k : ℕ) :
    ∃ S : E →ₗ[𝕜] F,
      Module.finrank 𝕜 (LinearMap.range S) ≤ k ∧
      ∀ x, ‖(T - S) x‖ ≤ T.singularValues k * ‖x‖  := by
  obtain ⟨P, hrank, hbound⟩ := exists_truncation_projection T k
  refine ⟨T ∘ₗ P, ?_, ?_⟩
  · rw [LinearMap.range_comp]
    exact (Submodule.finrank_map_le T (LinearMap.range P)).trans hrank
  · intro x
    rw [LinearMap.sub_apply, LinearMap.comp_apply]
    exact hbound x


end Problems.LinearAlgebra.eckart_young
