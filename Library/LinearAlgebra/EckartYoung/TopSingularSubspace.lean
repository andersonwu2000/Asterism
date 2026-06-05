import Library.LinearAlgebra.EckartYoung.EigenExpansion
import Library.LinearAlgebra.EckartYoung.SingularEigenRelations
import Mathlib

open Library.LinearAlgebra.EckartYoung.EigenExpansion
open Library.LinearAlgebra.EckartYoung.SingularEigenRelations

namespace Library.LinearAlgebra.EckartYoung.TopSingularSubspace

-- finrank_span_top_singular_eigenvectors: finrank_span_eq_card + Orthonormal.linearIndependent
-- The span of the first k+1 eigenvectors of T†T has dimension k+1.
-- Uses that Fin.castLE is injective so the restriction to Fin(k+1) stays linearly independent.
theorem finrank_span_top_singular_eigenvectors {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
    (T : E →ₗ[𝕜] F) (k : ℕ) (hk : k < Module.finrank 𝕜 E) :
    Module.finrank 𝕜 (Submodule.span 𝕜 (Set.range (fun i : Fin (k + 1) =>
      (T.isSymmetric_adjoint_comp_self.eigenvectorBasis
    (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E)) (Fin.castLE hk i)))) = k + 1 := by
  let hb := T.isSymmetric_adjoint_comp_self.eigenvectorBasis rfl
  have hli : LinearIndependent 𝕜 (fun i : Fin (k + 1) => hb (Fin.castLE hk i)) :=
    hb.orthonormal.linearIndependent.comp _ (Fin.castLE_injective _)
  rw [finrank_span_eq_card hli, Fintype.card_fin]

-- finrank_span_top_singular_eigenvectors_2: finrank_span_eq_card + Orthonormal.linearIndependent
-- Identical statement to finrank_span_top_singular_eigenvectors; same proof applies.
theorem finrank_span_top_singular_eigenvectors_2 {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
    (T : E →ₗ[𝕜] F) (k : ℕ) (hk : k < Module.finrank 𝕜 E) :
    Module.finrank 𝕜 (Submodule.span 𝕜 (Set.range (fun i : Fin (k + 1) =>
      (T.isSymmetric_adjoint_comp_self.eigenvectorBasis
        (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E)) (Fin.castLE hk i)))) = k + 1 := by
  let hb := T.isSymmetric_adjoint_comp_self.eigenvectorBasis rfl
  have hli : LinearIndependent 𝕜 (fun i : Fin (k + 1) => hb (Fin.castLE hk i)) :=
    hb.orthonormal.linearIndependent.comp _ (Fin.castLE_injective _)
  rw [finrank_span_eq_card hli, Fintype.card_fin]

-- Per-coordinate spectral bound `σ_k²‖⟪b_i,x⟫‖² ≤ λ_i‖⟪b_i,x⟫‖²`, split on `i ≤ k`.
-- Case `(i:ℕ) ≤ k`: `σ_k² ≤ λ_i` (`sq_singular_k_le_eigenvalue`, antitone eigenvalues
--   + `sq_singularValues_fin`), then `mul_le_mul_of_nonneg_right` against `‖⟪b_i,x⟫‖² ≥ 0`.
-- Case `k < (i:ℕ)`: `⟪b_i,x⟫ = 0` (`inner_eigenvector_high_eq_zero`, orthogonality of the
--   eigenbasis to the top-(k+1) span containing `x`), so both sides vanish (`simp`).
theorem termwise_eigenvalue_bound {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
    (T : E →ₗ[𝕜] F) (k : ℕ) (hk : k < Module.finrank 𝕜 E)
    (x : E) (hx : x ∈ Submodule.span 𝕜 (Set.range (fun i : Fin (k + 1) =>
      (T.isSymmetric_adjoint_comp_self.eigenvectorBasis
        (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E)) (Fin.castLE hk i))))
    (i : Fin (Module.finrank 𝕜 E)) :
    (T.singularValues k) ^ 2
        * ‖inner 𝕜 (T.isSymmetric_adjoint_comp_self.eigenvectorBasis rfl i) x‖ ^ 2
      ≤ T.isSymmetric_adjoint_comp_self.eigenvalues rfl i
        * ‖inner 𝕜 (T.isSymmetric_adjoint_comp_self.eigenvectorBasis rfl i) x‖ ^ 2  := by
  by_cases hik : (i : ℕ) ≤ k
  · have h_eig := sq_singular_k_le_eigenvalue T k hk i hik
    exact mul_le_mul_of_nonneg_right h_eig (sq_nonneg _)
  · have h_orth := inner_eigenvector_high_eq_zero T k hk x hx i (not_le.mp hik)
    rw [h_orth]; simp

-- Termwise σ_k²‖⟨b_i,x⟩‖² ≤ λ_i‖⟨b_i,x⟩‖²: split on (i:ℕ) ≤ k.
-- Low index (eigen_ge_low): σ_k² = λ_k ≤ λ_i, scale by nonneg ‖⟨b_i,x⟩‖².
-- High index (inner_zero_high): x in top-(k+1) span ⇒ ⟨b_i,x⟩ = 0, both sides vanish.
-- Sub-goals drop the sum/Parseval: a scalar comparison and a coordinate-vanishing fact.
theorem eigen_pointwise_lower_bound {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
    (T : E →ₗ[𝕜] F) (k : ℕ) (hk : k < Module.finrank 𝕜 E)
    (x : E) (hx : x ∈ Submodule.span 𝕜 (Set.range (fun i : Fin (k + 1) =>
      (T.isSymmetric_adjoint_comp_self.eigenvectorBasis
        (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E)) (Fin.castLE hk i)))) :
    ∀ i, (T.singularValues k)^2 * ‖inner 𝕜
        ((T.isSymmetric_adjoint_comp_self.eigenvectorBasis
          (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E)) i) x‖^2
      ≤ (T.isSymmetric_adjoint_comp_self.eigenvalues
          (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E) i)
        * ‖inner 𝕜 ((T.isSymmetric_adjoint_comp_self.eigenvectorBasis
          (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E)) i) x‖^2  := by
  intro i
  by_cases hi : (i : ℕ) ≤ k
  · -- low index: σ_k² = λ_k ≤ λ_i, scale by the nonneg coefficient ‖⟨b_i,x⟩‖²
    have hle : (T.singularValues k)^2 ≤ T.isSymmetric_adjoint_comp_self.eigenvalues
        (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E) i := eigen_ge_low T k hk i hi
    exact mul_le_mul_of_nonneg_right hle (sq_nonneg _)
  · -- high index: x lies in the top-(k+1) span, so the coordinate ⟨b_i,x⟩ vanishes
    have hz : (inner 𝕜 ((T.isSymmetric_adjoint_comp_self.eigenvectorBasis
        (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E)) i) x : 𝕜) = 0 :=
      inner_zero_high T k hk x hx i (by omega)
    rw [hz]
    simp

-- σ_k²‖x‖² ≤ ∑ λ_i‖⟨b_i,x⟩‖² for x in the top-(k+1) right-singular span.
-- Parseval (`sum_sq_norm_inner_right`) rewrites ‖x‖² = ∑‖⟨b_i,x⟩‖²; distribute σ_k²
-- into the sum, then compare termwise via the single sub-goal `eigen_pointwise_lower_bound`:
--   σ_k²‖⟨b_i,x⟩‖² ≤ λ_i‖⟨b_i,x⟩‖² (λ_i ≥ σ_k²=λ_k for i≤k; ⟨b_i,x⟩=0 for i>k).
-- Sub-goal is strictly simpler: pointwise, no sum, no Parseval.

theorem sum_eigen_lower_bound {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
    (T : E →ₗ[𝕜] F) (k : ℕ) (hk : k < Module.finrank 𝕜 E) :
    ∀ x ∈ Submodule.span 𝕜 (Set.range (fun i : Fin (k + 1) =>
      (T.isSymmetric_adjoint_comp_self.eigenvectorBasis
        (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E)) (Fin.castLE hk i))),
      (T.singularValues k)^2 * ‖x‖^2 ≤ ∑ i, (T.isSymmetric_adjoint_comp_self.eigenvalues
        (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E) i)
      * ‖inner 𝕜 ((T.isSymmetric_adjoint_comp_self.eigenvectorBasis
        (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E)) i) x‖^2  := by
  intro x hx
  have hpar : ‖x‖^2 = ∑ i, ‖inner 𝕜 ((T.isSymmetric_adjoint_comp_self.eigenvectorBasis
        (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E)) i) x‖^2 :=
    (OrthonormalBasis.sum_sq_norm_inner_right _ x).symm
  have hpt := eigen_pointwise_lower_bound T k hk x hx
  calc (T.singularValues k)^2 * ‖x‖^2
      = ∑ i, (T.singularValues k)^2 * ‖inner 𝕜
          ((T.isSymmetric_adjoint_comp_self.eigenvectorBasis
            (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E)) i) x‖^2 := by
        rw [hpar, Finset.mul_sum]
    _ ≤ ∑ i, (T.isSymmetric_adjoint_comp_self.eigenvalues
          (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E) i)
        * ‖inner 𝕜 ((T.isSymmetric_adjoint_comp_self.eigenvectorBasis
          (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E)) i) x‖^2 :=
        Finset.sum_le_sum (fun i _ => hpt i)

-- Spectral lower bound on the top-(k+1) right-singular span: reduce `σ_k‖x‖ ≤ ‖T x‖`
-- to its square `σ_k²‖x‖² ≤ ‖T x‖²` (via `le_of_sq_le_sq`), then diagonalize the Gram
-- operator `T†∘T` in its eigenbasis. Two sub-goals:
--   `re_inner_symm_eq_sum_eigenvalues_2` — the Rayleigh identity
--     `re⟪Sx,x⟫ = ∑ λ_i ‖⟪b_i,x⟫‖²` for a symmetric `S` (here `S = T†∘T`);
--   `termwise_eigenvalue_bound` — per-coordinate `σ_k²‖⟪b_i,x⟫‖² ≤ λ_i‖⟪b_i,x⟫‖²`
--     (antitone eigenvalues for `i ≤ k`, orthogonality `⟪b_i,x⟫=0` for `i > k`).
-- Summing the termwise bound over the orthonormal eigenbasis (`sum_sq_norm_inner_right`
-- collapses `∑‖⟪b_i,x⟫‖² = ‖x‖²`) yields the squared bound; `‖T x‖² = re⟪T†T x,x⟫`.
theorem norm_lower_bound_top_singular_span {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
    (T : E →ₗ[𝕜] F) (k : ℕ) (hk : k < Module.finrank 𝕜 E) :
    ∀ x ∈ Submodule.span 𝕜 (Set.range (fun i : Fin (k + 1) =>
      (T.isSymmetric_adjoint_comp_self.eigenvectorBasis
        (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E)) (Fin.castLE hk i))),
      T.singularValues k * ‖x‖ ≤ ‖T x‖  := by
  intro x hx
  -- ‖T x‖² = re⟪(T†∘T) x, x⟫
  have hTx : ‖T x‖ ^ 2 = RCLike.re (inner 𝕜 ((LinearMap.adjoint T ∘ₗ T) x) x) := by
    rw [LinearMap.comp_apply, LinearMap.adjoint_inner_left, inner_self_eq_norm_sq]
  -- diagonalization of the Gram operator in its eigenbasis
  have h_id : RCLike.re (inner 𝕜 ((LinearMap.adjoint T ∘ₗ T) x) x)
      = ∑ i : Fin (Module.finrank 𝕜 E),
          T.isSymmetric_adjoint_comp_self.eigenvalues rfl i
            * ‖inner 𝕜 (T.isSymmetric_adjoint_comp_self.eigenvectorBasis rfl i) x‖ ^ 2 :=
    re_inner_symm_eq_sum_eigenvalues_2 (LinearMap.adjoint T ∘ₗ T)
      T.isSymmetric_adjoint_comp_self (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E) x
  -- per-coordinate bound: σ_k² weight ≤ eigenvalue weight (orthogonality + antitone)
  have h_term : ∀ i : Fin (Module.finrank 𝕜 E),
      (T.singularValues k) ^ 2
          * ‖inner 𝕜 (T.isSymmetric_adjoint_comp_self.eigenvectorBasis rfl i) x‖ ^ 2
        ≤ T.isSymmetric_adjoint_comp_self.eigenvalues rfl i
          * ‖inner 𝕜 (T.isSymmetric_adjoint_comp_self.eigenvectorBasis rfl i) x‖ ^ 2 :=
    fun i => termwise_eigenvalue_bound T k hk x hx i
  -- assemble the squared bound
  have h_sq : (T.singularValues k) ^ 2 * ‖x‖ ^ 2 ≤ ‖T x‖ ^ 2 := by
    rw [hTx, h_id,
      ← (T.isSymmetric_adjoint_comp_self.eigenvectorBasis rfl).sum_sq_norm_inner_right x,
      Finset.mul_sum]
    exact Finset.sum_le_sum fun i _ => h_term i
  -- squared → linear
  refine le_of_sq_le_sq ?_ (norm_nonneg (T x))
  rw [mul_pow]
  exact h_sq

-- Eckart–Young subspace lower bound: σ_k‖x‖ ≤ ‖Tx‖ on the top-(k+1) right-singular span.
-- Reduce to the squared form via the spectral diagonalization of T†T:
--  (1) `norm_sq_eq_sum_eigen`: ‖Tx‖² = ∑ λ_i ‖⟨b_i,x⟩‖²  (b,λ = eigbasis/eigvals of T†T)
--  (2) `sum_eigen_lower_bound`: σ_k²‖x‖² ≤ ∑ λ_i ‖⟨b_i,x⟩‖²  (subspace + descending eigvals)
-- Combine: σ_k²‖x‖² ≤ ‖Tx‖², rewrite as (σ_k‖x‖)² and take square roots.
theorem norm_lower_bound_top_singular_span_2 {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
    (T : E →ₗ[𝕜] F) (k : ℕ) (hk : k < Module.finrank 𝕜 E) :
    ∀ x ∈ Submodule.span 𝕜 (Set.range (fun i : Fin (k + 1) =>
      (T.isSymmetric_adjoint_comp_self.eigenvectorBasis
        (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E)) (Fin.castLE hk i))),
      T.singularValues k * ‖x‖ ≤ ‖T x‖  := by
  intro x hx
  have hid : ‖T x‖^2 = ∑ i, (T.isSymmetric_adjoint_comp_self.eigenvalues
        (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E) i)
      * ‖inner 𝕜 ((T.isSymmetric_adjoint_comp_self.eigenvectorBasis
        (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E)) i) x‖^2 :=
    norm_sq_eq_sum_eigen T x
  have hlb := sum_eigen_lower_bound T k hk x hx
  have hsq : (T.singularValues k)^2 * ‖x‖^2 ≤ ‖T x‖^2 := by rw [hid]; exact hlb
  have key : (T.singularValues k * ‖x‖)^2 ≤ ‖T x‖^2 := by rw [mul_pow]; exact hsq
  exact le_of_sq_le_sq key (norm_nonneg _)

-- Eckart–Young lower bound, spectral half: build the top-(k+1) right-singular subspace.
-- `V` is the span of the first k+1 eigenvectors of `T† ∘ₗ T` (sorted by decreasing
-- eigenvalue σ_i²), supplied by `hT.eigenvectorBasis`. The goal's two conjuncts split into
-- two independent, strictly-smaller obligations on this fixed `V`:
--   `finrank_span_top_singular_eigenvectors` — `V` has dimension exactly k+1 (k+1 vectors
--     drawn from an orthonormal basis are linearly independent);
--   `norm_lower_bound_top_singular_span` — on `V`, `σ_k‖x‖ ≤ ‖T x‖` (the spectral content:
--     every eigenvalue contributing to `x` is ≥ σ_k²).
-- Combinator: `refine ⟨V, ?_, ?_⟩` then discharge each conjunct by its sub-goal.
theorem exists_top_singular_subspace {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
    (T : E →ₗ[𝕜] F) (k : ℕ) (hk : k < Module.finrank 𝕜 E) :
    ∃ V : Submodule 𝕜 E, Module.finrank 𝕜 V = k + 1 ∧
      ∀ x ∈ V, T.singularValues k * ‖x‖ ≤ ‖T x‖ := by
  classical
  refine ⟨Submodule.span 𝕜 (Set.range (fun i : Fin (k + 1) =>
    (T.isSymmetric_adjoint_comp_self.eigenvectorBasis
      (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E)) (Fin.castLE hk i))), ?_, ?_⟩
  · exact finrank_span_top_singular_eigenvectors T k hk
  · exact norm_lower_bound_top_singular_span T k hk

-- Eckart–Young, top-(k+1) right-singular subspace.
-- Witness: V = span of the top k+1 eigenvectors of T†T (`isSymmetric_adjoint_comp_self`'s
--   `eigenvectorBasis`, indexed by `Fin.castLE hk` into `Fin (k+1)`).
-- Sub-goal `finrank_span_top_singular_eigenvectors_2`: dim V = k+1 — the k+1 chosen vectors are
--   distinct members of an orthonormal basis, hence linearly independent, so their span has
--   finrank exactly k+1.
-- Sub-goal `norm_lower_bound_top_singular_span_2`: ∀ x ∈ V, σ_k‖x‖ ≤ ‖Tx‖ — the SVD spectral
--   content (T maps each top eigenvector to a singular value ≥ σ_k, descending).
-- Combine: exhibit V as the existential witness, pairing the two facts.
theorem top_singular_subspace_bound {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
    (T : E →ₗ[𝕜] F) (k : ℕ) (hk : k < Module.finrank 𝕜 E) :
    ∃ V : Submodule 𝕜 E, Module.finrank 𝕜 V = k + 1 ∧
      ∀ x ∈ V, T.singularValues k * ‖x‖ ≤ ‖T x‖  := by
  have h_finrank : Module.finrank 𝕜 (Submodule.span 𝕜 (Set.range (fun i : Fin (k + 1) =>
      (T.isSymmetric_adjoint_comp_self.eigenvectorBasis
        (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E)) (Fin.castLE hk i)))) = k + 1 :=
    finrank_span_top_singular_eigenvectors_2 T k hk
  have h_bound : ∀ x ∈ Submodule.span 𝕜 (Set.range (fun i : Fin (k + 1) =>
      (T.isSymmetric_adjoint_comp_self.eigenvectorBasis
        (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E)) (Fin.castLE hk i))),
      T.singularValues k * ‖x‖ ≤ ‖T x‖ :=
    norm_lower_bound_top_singular_span_2 T k hk
  exact ⟨_, h_finrank, h_bound⟩

end Library.LinearAlgebra.EckartYoung.TopSingularSubspace
