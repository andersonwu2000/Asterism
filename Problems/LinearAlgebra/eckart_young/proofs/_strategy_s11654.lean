import Mathlib
import Problems.LinearAlgebra.eckart_young.Defs
import Problems.LinearAlgebra.eckart_young.proofs.L_bottom_span_norm_le
import Problems.LinearAlgebra.eckart_young.proofs.L_norm_sub_starprojection_le

namespace Problems.LinearAlgebra.eckart_young

-- Eckart–Young membership (SVD content): build the rank-≤k truncation projection `P`.
-- Split on `k < finrank E`.  Degenerate branch (`finrank E ≤ k`): `P = id`, zero residual.
-- Main branch: take `K` = span of the top-k right singular vectors (eigenvectors of `T†T`),
-- and `P = K.starProjection`.  Two sub-goals factor the content:
--   • `bottom_span_norm_le` — `T` shrinks `Kᗮ` by `σ_k` (the spectral/SVD bound);
--   • `norm_sub_starprojection_le` — the orthogonal projection is norm non-increasing.
-- finrank(range P) = finrank K ≤ k via `range_starProjection` + `finrank_range_le_card`;
-- `(T-S)x = T(x - Px)` with `x - Px ∈ Kᗮ` chains the two bounds with the contraction.
theorem s11654 {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
    (T : E →ₗ[𝕜] F) (k : ℕ) :
    ∃ P : E →ₗ[𝕜] E,
      Module.finrank 𝕜 (LinearMap.range P) ≤ k ∧
      ∀ x, ‖T x - T (P x)‖ ≤ T.singularValues k * ‖x‖  := by
  by_cases hk : k < Module.finrank 𝕜 E
  · -- Truncation projection onto the span of the top-k right singular vectors.
    -- Abstract that span as `K`: it has finrank ≤ k and `T` shrinks its
    -- orthogonal complement by `σ_k` (the `bottom_span_norm_le` sub-goal).
    obtain ⟨K, hKfr, hKbound⟩ :
        ∃ K : Submodule 𝕜 E, Module.finrank 𝕜 K ≤ k ∧
          ∀ y ∈ Kᗮ, ‖T y‖ ≤ T.singularValues k * ‖y‖ := by
      refine ⟨Submodule.span 𝕜 (Set.range (fun i : Fin k =>
        (T.isSymmetric_adjoint_comp_self.eigenvectorBasis
          (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E)) (Fin.castLE hk.le i))), ?_, ?_⟩
      · simpa using finrank_range_le_card (fun i : Fin k =>
          (T.isSymmetric_adjoint_comp_self.eigenvectorBasis
            (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E)) (Fin.castLE hk.le i))
      · exact bottom_span_norm_le T k hk
    refine ⟨K.starProjection.toLinearMap, ?_, ?_⟩
    · have hrange : LinearMap.range K.starProjection.toLinearMap = K := K.range_starProjection
      rw [hrange]; exact hKfr
    · intro x
      have hmem : x - K.starProjection x ∈ Kᗮ := K.sub_starProjection_mem_orthogonal x
      have hbound := hKbound _ hmem
      have hcontract : ‖x - K.starProjection x‖ ≤ ‖x‖ := norm_sub_starprojection_le K x
      have heq : T x - T (K.starProjection.toLinearMap x) = T (x - K.starProjection x) :=
        (map_sub T x (K.starProjection x)).symm
      rw [heq]
      exact hbound.trans (mul_le_mul_of_nonneg_left hcontract (T.singularValues_nonneg k))
  · -- Degenerate case: finrank E ≤ k, identity already has rank ≤ k and zero residual.
    refine ⟨LinearMap.id, ?_, ?_⟩
    · rw [LinearMap.range_id, finrank_top]
      exact not_lt.mp hk
    · intro x
      simp only [LinearMap.id_coe, id_eq, sub_self, norm_zero]
      exact mul_nonneg (T.singularValues_nonneg k) (norm_nonneg x)


end Problems.LinearAlgebra.eckart_young
