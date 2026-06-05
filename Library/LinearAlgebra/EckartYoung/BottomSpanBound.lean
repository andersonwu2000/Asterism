import Library.LinearAlgebra.EckartYoung.Auxiliary
import Library.LinearAlgebra.EckartYoung.EigenExpansion
import Library.LinearAlgebra.EckartYoung.SingularEigenRelations
import Mathlib

open Library.LinearAlgebra.EckartYoung.Auxiliary
open Library.LinearAlgebra.EckartYoung.EigenExpansion
open Library.LinearAlgebra.EckartYoung.SingularEigenRelations

namespace Library.LinearAlgebra.EckartYoung.BottomSpanBound

-- Termwise bound `λ_i ‖⟨bᵢ,y⟩‖² ≤ σ_k² ‖⟨bᵢ,y⟩‖²` on `Kᗮ`, by case on `i` vs `k`.
-- `i ≥ k`: `λ_i ≤ σ_k²` by antitonicity (`eig_le_sigma_sq`), scaled by `‖⟨bᵢ,y⟩‖² ≥ 0`.
-- `i < k`: `bᵢ ∈ K` so `⟨bᵢ,y⟩ = 0` (`inner_eigvec_orthogonal`); both sides vanish.
theorem termwise_le_singular_k {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
    (T : E →ₗ[𝕜] F) (k : ℕ) (hk : k < Module.finrank 𝕜 E)
    (y : E) (hy : y ∈ (Submodule.span 𝕜 (Set.range (fun i : Fin k =>
      (T.isSymmetric_adjoint_comp_self.eigenvectorBasis
        (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E)) (Fin.castLE hk.le i))))ᗮ)
    (i : Fin (Module.finrank 𝕜 E)) :
    T.isSymmetric_adjoint_comp_self.eigenvalues
        (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E) i
        * ‖inner 𝕜 ((T.isSymmetric_adjoint_comp_self.eigenvectorBasis
            (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E)) i) y‖ ^ 2
      ≤ (T.singularValues k) ^ 2
        * ‖inner 𝕜 ((T.isSymmetric_adjoint_comp_self.eigenvectorBasis
            (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E)) i) y‖ ^ 2  := by
  by_cases h : k ≤ (i : ℕ)
  · have h_eig := eig_le_sigma_sq T k hk i h
    exact mul_le_mul_of_nonneg_right h_eig (sq_nonneg _)
  · have h_orth := inner_eigvec_orthogonal T k hk y hy i (not_le.mp h)
    rw [h_orth]
    simp

-- On `Kᗮ` (K = span of the top-k right singular vectors of `T`), bound `‖T y‖²` by `σ_k² ‖y‖²`.
-- Expand `‖T y‖²` in the eigenbasis of `T†T` (`h_eq`, the diagonalization identity), then bound
-- each summand termwise: `λ_i ‖⟨bᵢ,y⟩‖² ≤ σ_k² ‖⟨bᵢ,y⟩‖²` (`h_term` — vanishes for i<k since
-- y ⊥ K, and `λ_i ≤ σ_k²` for i≥k by antitonicity). Collapse `σ_k² ∑‖⟨bᵢ,y⟩‖² = σ_k² ‖y‖²`
-- via `sum_sq_norm_inner_right` and combine with `Finset.sum_le_sum`.
theorem bottom_span_norm_sq_le {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
    (T : E →ₗ[𝕜] F) (k : ℕ) (hk : k < Module.finrank 𝕜 E) :
    ∀ y ∈ (Submodule.span 𝕜 (Set.range (fun i : Fin k =>
      (T.isSymmetric_adjoint_comp_self.eigenvectorBasis
        (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E)) (Fin.castLE hk.le i))))ᗮ,
      ‖T y‖ ^ 2 ≤ (T.singularValues k) ^ 2 * ‖y‖ ^ 2  := by
  intro y hy
  have h_eq := norm_sq_eq_sum_eigen_2 T y
  rw [h_eq,
      ← (T.isSymmetric_adjoint_comp_self.eigenvectorBasis
        (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E)).sum_sq_norm_inner_right y,
      Finset.mul_sum]
  exact Finset.sum_le_sum (fun i _ => termwise_le_singular_k T k hk y hy i)

-- On `Kᗮ` (K = span of the top-k right singular vectors of `T`), `T` shrinks by `σ_k`.
-- Reduce to the squared bound `‖T y‖² ≤ σ_k² ‖y‖²` (the inner-product / eigenvalue content,
-- delegated to `bottom_span_norm_sq_le`), then lift through `le_of_sq_le_sq` since both
-- `σ_k * ‖y‖` and the norms are nonnegative.
theorem bottom_span_norm_le {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
    (T : E →ₗ[𝕜] F) (k : ℕ) (hk : k < Module.finrank 𝕜 E) :
    ∀ y ∈ (Submodule.span 𝕜 (Set.range (fun i : Fin k =>
      (T.isSymmetric_adjoint_comp_self.eigenvectorBasis
        (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E)) (Fin.castLE hk.le i))))ᗮ,
      ‖T y‖ ≤ T.singularValues k * ‖y‖  := by
  intro y hy
  have hsq : ‖T y‖ ^ 2 ≤ (T.singularValues k * ‖y‖) ^ 2 := by
    rw [mul_pow]
    exact bottom_span_norm_sq_le T k hk y hy
  exact le_of_sq_le_sq hsq (mul_nonneg (T.singularValues_nonneg k) (norm_nonneg _))

-- Eckart–Young membership (SVD content): build the rank-≤k truncation projection `P`.
-- Split on `k < finrank E`.  Degenerate branch (`finrank E ≤ k`): `P = id`, zero residual.
-- Main branch: take `K` = span of the top-k right singular vectors (eigenvectors of `T†T`),
-- and `P = K.starProjection`.  Two sub-goals factor the content:
--   • `bottom_span_norm_le` — `T` shrinks `Kᗮ` by `σ_k` (the spectral/SVD bound);
--   • `norm_sub_starprojection_le` — the orthogonal projection is norm non-increasing.
-- finrank(range P) = finrank K ≤ k via `range_starProjection` + `finrank_range_le_card`;
-- `(T-S)x = T(x - Px)` with `x - Px ∈ Kᗮ` chains the two bounds with the contraction.
theorem exists_truncation_projection {𝕜 : Type*} [RCLike 𝕜]
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

-- Membership direction of Eckart–Young: build a rank-≤k truncation `S` whose
-- residual is pointwise bounded by σ_k.  Factor `S = T ∘ₗ P` through a rank-≤k
-- projection `P : E →ₗ E` (sub-goal `exists_truncation_projection`, the SVD/
-- spectral content).  Then `range (T∘ₗP) = T.map (range P)` has finrank ≤
-- finrank (range P) ≤ k (`Submodule.finrank_map_le`), and `(T-S) x = T x - T(Px)`
-- (`LinearMap.sub_apply`/`comp_apply`) inherits the pointwise bound directly.

theorem exists_truncation_pointwise_le_singularvalue {𝕜 : Type*} [RCLike 𝕜]
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

-- Reduce the operator-norm membership bound to a *pointwise* truncation bound.
-- Sub-goal `exists_truncation_pointwise_le_singularvalue` builds the rank-≤k
-- truncation S with the elementary pointwise estimate ‖(T−S) x‖ ≤ σ_k‖x‖; the
-- operator norm bound then follows by `opNorm_le_bound` (real work, no opNorm/CLM
-- machinery in the sub-goal).
theorem exists_truncation_norm_le_singularvalue {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
    (T : E →ₗ[𝕜] F) (k : ℕ) :
    ∃ S : E →ₗ[𝕜] F,
      Module.finrank 𝕜 (LinearMap.range S) ≤ k ∧
      ‖LinearMap.toContinuousLinearMap (T - S)‖ ≤ T.singularValues k  := by
  obtain ⟨S, hrank, hpt⟩ := exists_truncation_pointwise_le_singularvalue T k
  refine ⟨S, hrank, ?_⟩
  apply ContinuousLinearMap.opNorm_le_bound _ (T.singularValues_nonneg k)
  intro x
  have hpt' := hpt x
  rwa [LinearMap.coe_toContinuousLinearMap']

end Library.LinearAlgebra.EckartYoung.BottomSpanBound
