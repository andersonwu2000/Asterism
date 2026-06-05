import Library.LinearAlgebra.EckartYoung.Auxiliary
import Library.LinearAlgebra.EckartYoung.BottomSpanBound
import Library.LinearAlgebra.EckartYoung.TopSingularSubspace
import Mathlib

open Library.LinearAlgebra.EckartYoung.Auxiliary
open Library.LinearAlgebra.EckartYoung.BottomSpanBound
open Library.LinearAlgebra.EckartYoung.TopSingularSubspace

namespace Library.LinearAlgebra.EckartYoung.EckartYoung

-- Eckart–Young lower bound: a kernel vector of S on which T cannot shrink below σ_k.
-- `exists_top_singular_subspace` builds the (k+1)-dim top right-singular span V on which
-- `σ_k‖x‖ ≤ ‖T x‖` holds (the spectral content). `ker_finrank_ge` gives
-- `finrank E ≤ finrank(ker S) + k` (rank–nullity). Since
-- `finrank V + finrank(ker S) = (k+1) + finrank(ker S) > finrank E`, the 𝕜-version
-- `exists_nonzero_mem_inf_of_finrank` (dimension-count intersection) yields a nonzero
-- `x ∈ V ∩ ker S`; `S x = 0` from `mem_ker`, `σ_k‖x‖ ≤ ‖T x‖` from V's bound.
theorem exists_kernel_vector_norm_lower {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
    (T : E →ₗ[𝕜] F) (S : E →ₗ[𝕜] F) (k : ℕ)
    (hk : k < Module.finrank 𝕜 E)
    (hrank : Module.finrank 𝕜 (LinearMap.range S) ≤ k) :
    ∃ x : E, x ≠ 0 ∧ S x = 0 ∧ T.singularValues k * ‖x‖ ≤ ‖T x‖  := by
  obtain ⟨V, hVdim, hVbound⟩ := exists_top_singular_subspace T k hk
  have hker : Module.finrank 𝕜 E ≤ Module.finrank 𝕜 (LinearMap.ker S) + k :=
    ker_finrank_ge S k hrank
  obtain ⟨x, hxV, hxker, hxne⟩ :=
    exists_nonzero_mem_inf_of_finrank V (LinearMap.ker S) (by rw [hVdim]; omega)
  exact ⟨x, hxne, LinearMap.mem_ker.mp hxker, hVbound x hxV⟩

-- Eckart–Young lower bound, kernel witness: a nonzero x killed by S with σ_k‖x‖ ≤ ‖T x‖.
-- Sub-goal `top_singular_subspace_bound`: the top-(k+1) right-singular span V (dim k+1)
--   on which T is bounded below by σ_k (the SVD content).
-- Rank–nullity (`finrank_range_add_finrank_ker`) gives dim(ker S) ≥ n−k inline, so
--   dim V + dim(ker S) ≥ (k+1)+(n−k) > n; sub-goal `exists_nonzero_mem_inf_of_finrank_2`
--   (abstract dimension-counting) yields a nonzero x ∈ V ∩ ker S. Then S x = 0 and the
--   V-bound give the conclusion.
theorem kernel_witness_singularvalue {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
    (T : E →ₗ[𝕜] F) (k : ℕ) (S : E →ₗ[𝕜] F)
    (hrank : Module.finrank 𝕜 (LinearMap.range S) ≤ k)
    (hk : k < Module.finrank 𝕜 E) :
    ∃ x : E, x ≠ 0 ∧ S x = 0 ∧ T.singularValues k * ‖x‖ ≤ ‖T x‖  := by
  have h_top : ∃ V : Submodule 𝕜 E, Module.finrank 𝕜 V = k + 1 ∧
      ∀ x ∈ V, T.singularValues k * ‖x‖ ≤ ‖T x‖ := top_singular_subspace_bound T k hk
  have h_ker : Module.finrank 𝕜 E ≤ Module.finrank 𝕜 (LinearMap.ker S) + k := by
    have h := S.finrank_range_add_finrank_ker (K := 𝕜)
    omega
  obtain ⟨V, hVdim, hVbound⟩ := h_top
  have hcount : Module.finrank 𝕜 E < Module.finrank 𝕜 V + Module.finrank 𝕜 (LinearMap.ker S) := by
    rw [hVdim]; omega
  obtain ⟨x, hxV, hxker, hx0⟩ := exists_nonzero_mem_inf_of_finrank_2 V (LinearMap.ker S) hcount
  exact ⟨x, hx0, LinearMap.mem_ker.mp hxker, hVbound x hxV⟩

-- Decompose `σ_k ∈ lowerBounds {‖T-S‖ : rank S ≤ k}` into two pieces.
-- After unfolding to `σ_k ≤ ‖T-S‖`, split on `k < finrank E`:
--  • main case: `exists_kernel_vector_norm_lower` gives `x ≠ 0` with `S x = 0`
--    and `σ_k‖x‖ ≤ ‖T x‖`; on `x`, `(T-S) x = T x`, so `opnorm_ge_of_vector_bound`
--    lifts the pointwise bound to the operator norm.
--  • degenerate case `finrank E ≤ k`: `σ_k = 0 ≤ ‖T-S‖`.
theorem eckart_young_lower_bound {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
    (T : E →ₗ[𝕜] F) (k : ℕ) :
    (T.singularValues k) ∈ lowerBounds (setOf fun r : ℝ => ∃ S : E →ₗ[𝕜] F,
        Module.finrank 𝕜 (LinearMap.range S) ≤ k ∧
        r = ‖LinearMap.toContinuousLinearMap (T - S)‖)  := by
  intro r hr
  obtain ⟨S, hrank, hr⟩ := hr
  subst hr
  by_cases hk : k < Module.finrank 𝕜 E
  · obtain ⟨x, hx0, hSx, hbound⟩ := exists_kernel_vector_norm_lower T S k hk hrank
    have key : T.singularValues k * ‖x‖ ≤ ‖(T - S) x‖ := by
      rw [LinearMap.sub_apply, hSx, sub_zero]; exact hbound
    exact opnorm_ge_of_vector_bound (T - S) x (T.singularValues k) hx0 key
  · rw [T.singularValues_of_finrank_le (not_lt.mp hk)]
    exact norm_nonneg _

-- Lower bound: σ_k ≤ ‖T−S‖ for every rank-≤k S. Unfold the lowerBounds set,
-- split on whether k indexes a real singular value.
-- Sub-goal `kernel_witness_singularvalue`: rank-nullity + top-(k+1) right-singular
-- span ∩ ker S yields a nonzero x with S x = 0 and σ_k‖x‖ ≤ ‖T x‖.
-- Sub-goal `opnorm_ge_of_pointwise_bound`: a pointwise lower bound on a unit-direction
-- lifts to the operator norm. Degenerate branch (finrank E ≤ k): σ_k = 0 ≤ ‖·‖.
theorem singularvalue_mem_lowerbounds {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
    (T : E →ₗ[𝕜] F) (k : ℕ) :
    (T.singularValues k) ∈ lowerBounds (setOf fun r : ℝ =>
      ∃ S : E →ₗ[𝕜] F, Module.finrank 𝕜 (LinearMap.range S) ≤ k ∧
        r = ‖LinearMap.toContinuousLinearMap (T - S)‖)  := by
  intro r hr
  obtain ⟨S, hrank, rfl⟩ := hr
  by_cases hk : k < Module.finrank 𝕜 E
  · obtain ⟨x, hx, hSx, hbound⟩ := kernel_witness_singularvalue T k S hrank hk
    have key : T.singularValues k * ‖x‖ ≤ ‖(T - S) x‖ := by
      rw [LinearMap.sub_apply, hSx, sub_zero]; exact hbound
    exact opnorm_ge_of_pointwise_bound (T - S) x (T.singularValues k) hx key
  · rw [T.singularValues_of_finrank_le (not_lt.mp hk)]
    exact norm_nonneg _

-- Membership = the upper-bound construction half. Build a rank-≤k truncation `S`
-- with ‖T−S‖ ≤ σ_k (`exists_truncation_norm_le_singularvalue`); the re-declared
-- lower-bound sub-goal gives σ_k ≤ ‖T−S‖ for that same S (`singularvalue_mem_lowerbounds`,
-- dedupe-aliases the lower-bound sibling), so antisymmetry pins ‖T−S‖ = σ_k.
theorem eckart_young_membership {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
    (T : E →ₗ[𝕜] F) (k : ℕ) :
    (T.singularValues k) ∈ (setOf fun r : ℝ => ∃ S : E →ₗ[𝕜] F,
        Module.finrank 𝕜 (LinearMap.range S) ≤ k ∧
        r = ‖LinearMap.toContinuousLinearMap (T - S)‖)  := by
  obtain ⟨S, hrank, hle⟩ := exists_truncation_norm_le_singularvalue T k
  refine ⟨S, hrank, ?_⟩
  have hge : T.singularValues k ≤ ‖LinearMap.toContinuousLinearMap (T - S)‖ :=
    singularvalue_mem_lowerbounds T k ⟨S, hrank, rfl⟩
  exact le_antisymm hge hle

-- Eckart–Young: split `IsLeast S (σ_k)` into its two defining conjuncts —
-- (A) membership: σ_k is attained by some rank-≤k S, and
-- (B) lower bound: every rank-≤k S has error ≥ σ_k. `⟨_, _⟩` reassembles IsLeast.
theorem main : ∀ {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
    (T : E →ₗ[𝕜] F) (k : ℕ),
    IsLeast
      (setOf fun r : ℝ => ∃ S : E →ₗ[𝕜] F,
        Module.finrank 𝕜 (LinearMap.range S) ≤ k ∧
        r = ‖LinearMap.toContinuousLinearMap (T - S)‖)
      (T.singularValues k)  := by
  intro 𝕜 _ E F _ _ _ _ _ _ T k
  have h_mem := eckart_young_membership T k
  have h_lb := eckart_young_lower_bound T k
  exact ⟨h_mem, h_lb⟩

end Library.LinearAlgebra.EckartYoung.EckartYoung
