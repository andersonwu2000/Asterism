import Library.LinearAlgebra.EckartYoung.Auxiliary
import Library.LinearAlgebra.EckartYoung.BottomSpanBound
import Library.LinearAlgebra.EckartYoung.TopSingularSubspace
import Mathlib.Analysis.InnerProductSpace.Adjoint
import Mathlib.Analysis.InnerProductSpace.Projection.Basic
import Mathlib.Analysis.InnerProductSpace.SingularValues
import Mathlib.Analysis.InnerProductSpace.Spectrum
import Mathlib.Analysis.Normed.Operator.Basic
import Mathlib.Analysis.RCLike.Basic
import Mathlib.LinearAlgebra.Dimension.Constructions
import Mathlib.LinearAlgebra.FiniteDimensional.Lemmas
import Mathlib.Topology.Algebra.Module.FiniteDimension

/-!
# Eckart–Young–Mirsky theorem

This file proves the **Eckart–Young–Mirsky theorem**: for a linear map $T : E \to F$ between
finite-dimensional inner product spaces over an `RCLike` field $𝕜$, the $k$-th singular value
$\sigma_k(T)$ is the minimum operator-norm distance from $T$ to all linear maps of rank at most
$k$. Concretely, $\sigma_k(T) = \min \{ \|T - S\| \mid S : E \to F,\, \operatorname{rank}(S)
\le k \}$.

## Main statements

- `singularValues_isLeast`: $\sigma_k(T)$ is the least element of the set
  $\{ \|T - S\| \mid S : E \to_{ₗ[𝕜]} F,\, \operatorname{rank}(S) \le k \}$.

## Implementation notes

The proof proceeds in two directions.

**Upper bound** (`exists_truncation_norm_le_singularvalue`): we exhibit an explicit rank-$k$
truncation $S = T \circ P$, where $P$ is the orthogonal projection onto the span of the first $k$
right-singular vectors of $T$. The bound $\|T - S\| \le \sigma_k(T)$ follows from the spectral
estimate on $T|_{(\operatorname{span})^\perp}$ provided by `BottomSpanBound`.

**Lower bound** (`singularvalue_mem_lowerbounds`): given any $S$ with $\operatorname{rank}(S) \le
k$, a dimension count (rank–nullity for $S$ combined with the $(k+1)$-dimensional top
right-singular subspace from `TopSingularSubspace`) yields a nonzero $x \in \ker S$ with
$\sigma_k(T)\|x\| \le \|Tx\|$, giving $\sigma_k(T) \le \|T - S\|$.
-/

open Library.LinearAlgebra.EckartYoung.Auxiliary
open Library.LinearAlgebra.EckartYoung.BottomSpanBound
open Library.LinearAlgebra.EckartYoung.TopSingularSubspace

namespace Library.LinearAlgebra.EckartYoung.EckartYoung

-- The module path forces a repeated `EckartYoung` component; the namespace line is fixed.
set_option linter.dupNamespace false

/-- Given a linear map `T : E →ₗ[𝕜] F` and `k : ℕ`, there exists an orthogonal projection
`P : E →ₗ[𝕜] E` with `finrank (range P) ≤ k` such that `‖T x - T (P x)‖ ≤ σ_k(T) · ‖x‖`
for every `x : E`.

This is the key upper-bound step: $P$ projects onto the span of the first $k$ right-singular
vectors, and the complementary subspace $(\operatorname{span})^\perp$ satisfies the spectral
estimate from `BottomSpanBound`. -/
theorem exists_truncation_projection {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
    (T : E →ₗ[𝕜] F) (k : ℕ) :
    ∃ P : E →ₗ[𝕜] E,
      Module.finrank 𝕜 (LinearMap.range P) ≤ k ∧
      ∀ x, ‖T x - T (P x)‖ ≤ T.singularValues k * ‖x‖ := by
  by_cases hk : k < Module.finrank 𝕜 E
  · obtain ⟨K, hKfr, hKbound⟩ :
        ∃ K : Submodule 𝕜 E, Module.finrank 𝕜 K ≤ k ∧
          ∀ y ∈ Kᗮ, ‖T y‖ ≤ T.singularValues k * ‖y‖ := by
      refine ⟨Submodule.span 𝕜 (Set.range (fun i : Fin k =>
        (T.isSymmetric_adjoint_comp_self.eigenvectorBasis
          (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E)) (Fin.castLE hk.le i))), ?_, ?_⟩
      · simpa using finrank_range_le_card (fun i : Fin k =>
          (T.isSymmetric_adjoint_comp_self.eigenvectorBasis
            (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E)) (Fin.castLE hk.le i))
      · exact Library.LinearAlgebra.EckartYoung.BottomSpanBound.bottom_span_norm_le T k hk
    refine ⟨K.starProjection.toLinearMap, ?_, ?_⟩
    · rw [K.range_starProjection]; exact hKfr
    · intro x
      have hmem : x - K.starProjection x ∈ Kᗮ := K.sub_starProjection_mem_orthogonal x
      have hbound := hKbound _ hmem
      have hcontract :=
        Library.LinearAlgebra.EckartYoung.BottomSpanBound.norm_sub_starprojection_le K x
      have heq : T x - T (K.starProjection.toLinearMap x) = T (x - K.starProjection x) :=
        (map_sub T x (K.starProjection x)).symm
      rw [heq]
      exact hbound.trans (mul_le_mul_of_nonneg_left hcontract (T.singularValues_nonneg k))
  · refine ⟨LinearMap.id, ?_, ?_⟩
    · rw [LinearMap.range_id, finrank_top]; exact not_lt.mp hk
    · intro x
      simp only [LinearMap.id_coe, id_eq, sub_self, norm_zero]
      exact mul_nonneg (T.singularValues_nonneg k) (norm_nonneg x)

/-- Given `T : E →ₗ[𝕜] F` and `k : ℕ`, there exists a linear map `S : E →ₗ[𝕜] F` with
`finrank (range S) ≤ k` such that `‖(T - S) x‖ ≤ σ_k(T) · ‖x‖` for every `x : E`.

This is the pointwise form of the upper bound; the operator-norm form is
`exists_truncation_norm_le_singularvalue`. -/
theorem exists_truncation_pointwise_le_singularvalue {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
    (T : E →ₗ[𝕜] F) (k : ℕ) :
    ∃ S : E →ₗ[𝕜] F,
      Module.finrank 𝕜 (LinearMap.range S) ≤ k ∧
      ∀ x, ‖(T - S) x‖ ≤ T.singularValues k * ‖x‖ := by
  obtain ⟨P, hrank, hbound⟩ := exists_truncation_projection T k
  refine ⟨T ∘ₗ P, ?_, ?_⟩
  · rw [LinearMap.range_comp]
    exact (Submodule.finrank_map_le T (LinearMap.range P)).trans hrank
  · intro x
    rw [LinearMap.sub_apply, LinearMap.comp_apply]
    exact hbound x

/-- Given `T : E →ₗ[𝕜] F` and `k : ℕ`, there exists a linear map `S : E →ₗ[𝕜] F` with
`finrank (range S) ≤ k` such that `‖T - S‖ ≤ σ_k(T)` (operator norm).

This is the upper-bound half of the Eckart–Young–Mirsky theorem; combine with
`singularvalue_mem_lowerbounds` to obtain the full result `singularValues_isLeast`. -/
theorem exists_truncation_norm_le_singularvalue {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
    (T : E →ₗ[𝕜] F) (k : ℕ) :
    ∃ S : E →ₗ[𝕜] F,
      Module.finrank 𝕜 (LinearMap.range S) ≤ k ∧
      ‖LinearMap.toContinuousLinearMap (T - S)‖ ≤ T.singularValues k := by
  obtain ⟨S, hrank, hpt⟩ := exists_truncation_pointwise_le_singularvalue T k
  refine ⟨S, hrank, ?_⟩
  apply ContinuousLinearMap.opNorm_le_bound _ (T.singularValues_nonneg k)
  intro x
  have hpt' := hpt x
  rwa [LinearMap.coe_toContinuousLinearMap']

/-- If `S : E →ₗ[𝕜] F` has rank at most `k` and `k < finrank 𝕜 E`, then there exists a
nonzero vector `x : E` with `S x = 0` and `σ_k(T) · ‖x‖ ≤ ‖T x‖`.

The proof uses a dimension count: the $(k+1)$-dimensional top right-singular subspace $V$ of $T$
(from `exists_top_singular_subspace`) and $\ker S$ together satisfy
$\dim V + \dim(\ker S) > \dim E$, so their intersection contains a nonzero $x$; this $x$ lies in
$\ker S$ and satisfies the spectral lower bound for $T$ from $V$. -/
theorem kernel_witness_singularvalue {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
    (T : E →ₗ[𝕜] F) (k : ℕ) (S : E →ₗ[𝕜] F)
    (hrank : Module.finrank 𝕜 (LinearMap.range S) ≤ k)
    (hk : k < Module.finrank 𝕜 E) :
    ∃ x : E, x ≠ 0 ∧ S x = 0 ∧ T.singularValues k * ‖x‖ ≤ ‖T x‖ := by
  have h_top : ∃ V : Submodule 𝕜 E, Module.finrank 𝕜 V = k + 1 ∧
      ∀ x ∈ V, T.singularValues k * ‖x‖ ≤ ‖T x‖ := exists_top_singular_subspace T k hk
  have h_ker : Module.finrank 𝕜 E ≤ Module.finrank 𝕜 (LinearMap.ker S) + k := by
    have h := S.finrank_range_add_finrank_ker (K := 𝕜)
    omega
  obtain ⟨V, hVdim, hVbound⟩ := h_top
  have hcount : Module.finrank 𝕜 E <
      Module.finrank 𝕜 V + Module.finrank 𝕜 (LinearMap.ker S) := by
    rw [hVdim]; omega
  obtain ⟨x, hxV, hxker, hx0⟩ := exists_nonzero_mem_inf_of_finrank V (LinearMap.ker S) hcount
  exact ⟨x, hx0, LinearMap.mem_ker.mp hxker, hVbound x hxV⟩

/-- Alias for `kernel_witness_singularvalue` with `T` and `S` in the standard order for
lower-bound arguments.

If `S : E →ₗ[𝕜] F` has rank at most `k` and `k < finrank 𝕜 E`, there exists a nonzero `x : E`
with `S x = 0` and `σ_k(T) · ‖x‖ ≤ ‖T x‖`. -/
theorem exists_kernel_vector_norm_lower {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
    (T : E →ₗ[𝕜] F) (S : E →ₗ[𝕜] F) (k : ℕ)
    (hk : k < Module.finrank 𝕜 E)
    (hrank : Module.finrank 𝕜 (LinearMap.range S) ≤ k) :
    ∃ x : E, x ≠ 0 ∧ S x = 0 ∧ T.singularValues k * ‖x‖ ≤ ‖T x‖ :=
  Library.LinearAlgebra.EckartYoung.EckartYoung.kernel_witness_singularvalue
    T k S hrank hk

/-- The $k$-th singular value $\sigma_k(T)$ is a lower bound for the set
$\{ \|T - S\| \mid S : E \to_{ₗ[𝕜]} F,\, \operatorname{rank}(S) \le k \}$.

When `k < finrank 𝕜 E`, `kernel_witness_singularvalue` produces a nonzero `x ∈ ker S` with
`σ_k(T) · ‖x‖ ≤ ‖T x‖ = ‖(T - S) x‖`, which lifts to an operator-norm lower bound via
`opnorm_ge_of_pointwise_bound`. In the degenerate case `finrank 𝕜 E ≤ k` the singular value
vanishes and the bound is trivial. -/
theorem singularvalue_mem_lowerbounds {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
    (T : E →ₗ[𝕜] F) (k : ℕ) :
    (T.singularValues k) ∈ lowerBounds (setOf fun r : ℝ =>
      ∃ S : E →ₗ[𝕜] F, Module.finrank 𝕜 (LinearMap.range S) ≤ k ∧
        r = ‖LinearMap.toContinuousLinearMap (T - S)‖) := by
  intro r hr
  obtain ⟨S, hrank, rfl⟩ := hr
  by_cases hk : k < Module.finrank 𝕜 E
  · obtain ⟨x, hx, hSx, hbound⟩ := kernel_witness_singularvalue T k S hrank hk
    have key : T.singularValues k * ‖x‖ ≤ ‖(T - S) x‖ := by
      rw [LinearMap.sub_apply, hSx, sub_zero]; exact hbound
    exact opnorm_ge_of_pointwise_bound (T - S) x (T.singularValues k) hx key
  · rw [T.singularValues_of_finrank_le (not_lt.mp hk)]
    exact norm_nonneg _

/-- The $k$-th singular value $\sigma_k(T)$ is attained: it belongs to the set
$\{ \|T - S\| \mid S : E \to_{ₗ[𝕜]} F,\, \operatorname{rank}(S) \le k \}$.

The witness $S$ comes from `exists_truncation_norm_le_singularvalue`; equality follows by
combining the upper bound $\|T - S\| \le \sigma_k(T)$ with the lower bound
`singularvalue_mem_lowerbounds`. -/
theorem eckart_young_membership {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
    (T : E →ₗ[𝕜] F) (k : ℕ) :
    (T.singularValues k) ∈ (setOf fun r : ℝ => ∃ S : E →ₗ[𝕜] F,
        Module.finrank 𝕜 (LinearMap.range S) ≤ k ∧
        r = ‖LinearMap.toContinuousLinearMap (T - S)‖) := by
  obtain ⟨S, hrank, hle⟩ := exists_truncation_norm_le_singularvalue T k
  refine ⟨S, hrank, ?_⟩
  have hge : T.singularValues k ≤ ‖LinearMap.toContinuousLinearMap (T - S)‖ :=
    singularvalue_mem_lowerbounds T k ⟨S, hrank, rfl⟩
  exact le_antisymm hge hle

/-- **Eckart–Young–Mirsky theorem**: the $k$-th singular value $\sigma_k(T)$ is the least element
of the set $\{ \|T - S\| \mid S : E \to_{ₗ[𝕜]} F,\, \operatorname{rank}(S) \le k \}$.

Membership is given by `eckart_young_membership` (upper bound, attained by a rank-$k$
truncation) and minimality by `singularvalue_mem_lowerbounds` (lower bound via a dimension-count
kernel witness). -/
theorem singularValues_isLeast : ∀ {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
    (T : E →ₗ[𝕜] F) (k : ℕ),
    IsLeast
      (setOf fun r : ℝ => ∃ S : E →ₗ[𝕜] F,
        Module.finrank 𝕜 (LinearMap.range S) ≤ k ∧
        r = ‖LinearMap.toContinuousLinearMap (T - S)‖)
      (T.singularValues k) := by
  intro 𝕜 _ E F _ _ _ _ _ _ T k
  exact ⟨eckart_young_membership T k, singularvalue_mem_lowerbounds T k⟩

end Library.LinearAlgebra.EckartYoung.EckartYoung
