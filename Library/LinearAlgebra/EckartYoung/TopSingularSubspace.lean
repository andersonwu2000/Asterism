import Library.LinearAlgebra.EckartYoung.EigenExpansion
import Library.LinearAlgebra.EckartYoung.SingularEigenRelations
import Mathlib.Algebra.BigOperators.Ring.Finset
import Mathlib.Algebra.Module.Submodule.Lattice
import Mathlib.Algebra.Order.BigOperators.Group.Finset
import Mathlib.Algebra.Order.Ring.Abs
import Mathlib.Analysis.InnerProductSpace.Adjoint
import Mathlib.Analysis.InnerProductSpace.Basic
import Mathlib.Analysis.InnerProductSpace.Orthonormal
import Mathlib.Analysis.InnerProductSpace.PiL2
import Mathlib.Analysis.InnerProductSpace.SingularValues
import Mathlib.Analysis.InnerProductSpace.Spectrum
import Mathlib.Analysis.RCLike.Basic
import Mathlib.Data.Fin.SuccPred
import Mathlib.Data.Fintype.Card
import Mathlib.LinearAlgebra.Dimension.Constructions
import Mathlib.LinearAlgebra.Dimension.Finite
import Mathlib.LinearAlgebra.FiniteDimensional.Lemmas
import Mathlib.LinearAlgebra.LinearIndependent.Basic

/-!
# Top Singular Subspace

This file constructs the "top-$k$ singular subspace" of a bounded linear map
$T : E \to F$ between finite-dimensional inner product spaces over an `RCLike` field
$\mathbb{k}$, and proves the key norm lower bound used in the Eckart–Young theorem.

## Main statements

* `exists_nonzero_mem_inf_of_finrank` — if $\dim U + \dim W > \dim V$ then
  $U \cap W$ contains a nonzero vector (dimension-count argument over a general field).
* `finrank_le_finrank_ker_add` — rank–nullity gives
  $\dim E \le \dim \ker S + k$ when $\operatorname{rank} S \le k$.
* `finrank_span_top_singular_eigenvectors` — the span of the first $k+1$
  eigenvectors of $T^\dagger T$ has dimension $k+1$.
* `sum_eigen_lower_bound` — for every $x$ in that span, the sum of eigenvalue-weighted
  inner-product squares is bounded below by $\sigma_k(T)^2 \lVert x \rVert^2$.
* `norm_lower_bound_top_singular_span` — for every $x$ in the top-$k$ singular
  subspace, $\sigma_k(T) \lVert x \rVert \le \lVert T x \rVert$.
* `exists_top_singular_subspace` — there exists a $(k+1)$-dimensional subspace $V$
  satisfying the above lower bound; this is the main input to the Eckart–Young lower
  bound half.

## Implementation notes

The eigenbasis of $T^\dagger T$ is accessed via
`LinearMap.IsSymmetric.eigenvectorBasis` with a `rfl` proof that
`Module.finrank 𝕜 E = Module.finrank 𝕜 E`, following the convention used in
`EigenExpansion` and `SingularEigenRelations`.
-/

open Library.LinearAlgebra.EckartYoung.EigenExpansion
open Library.LinearAlgebra.EckartYoung.SingularEigenRelations

namespace Library.LinearAlgebra.EckartYoung.TopSingularSubspace

/-- If $\dim_K U + \dim_K W > \dim_K V$ then $U \cap W$ contains a nonzero vector.
This is the standard dimension-count intersection lemma, proved via
`Submodule.finrank_sup_add_finrank_inf_eq` and `Submodule.exists_mem_ne_zero_of_ne_bot`. -/
theorem exists_nonzero_mem_inf_of_finrank {K : Type*} [Field K]
    {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
    (U W : Submodule K V)
    (h : Module.finrank K V < Module.finrank K U + Module.finrank K W) :
    ∃ x : V, x ∈ U ∧ x ∈ W ∧ x ≠ 0 := by
  have hinf_pos : 0 < Module.finrank K (U ⊓ W : Submodule K V) := by
    have hsup_le : Module.finrank K (U ⊔ W : Submodule K V) ≤ Module.finrank K V :=
      Submodule.finrank_le _
    have heq := Submodule.finrank_sup_add_finrank_inf_eq U W
    omega
  have hinf_ne_bot : (U ⊓ W : Submodule K V) ≠ ⊥ := by
    intro heq
    rw [heq, finrank_bot] at hinf_pos
    exact Nat.lt_irrefl 0 hinf_pos
  obtain ⟨x, hxmem, hxne⟩ := Submodule.exists_mem_ne_zero_of_ne_bot hinf_ne_bot
  exact ⟨x, hxmem.1, hxmem.2, hxne⟩

/-- If the range of a linear map $S : E \to F$ has dimension at most $k$, then
$\dim E \le \dim \ker S + k$. This follows immediately from the rank–nullity theorem
`LinearMap.finrank_range_add_finrank_ker`. -/
theorem finrank_le_finrank_ker_add {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
    (S : E →ₗ[𝕜] F) (k : ℕ)
    (hrank : Module.finrank 𝕜 (LinearMap.range S) ≤ k) :
    Module.finrank 𝕜 E ≤ Module.finrank 𝕜 (LinearMap.ker S) + k := by
  have h := S.finrank_range_add_finrank_ker (K := 𝕜)
  omega

/-- The span of the first $k+1$ eigenvectors of $T^\dagger T$ (indexed by
`Fin (k + 1)` via `Fin.castLE hk`) has $\mathbb{k}$-dimension $k+1$.
This uses `Orthonormal.linearIndependent` composed with `Fin.castLE_injective`. -/
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

/-- For every $x$ in the span of the first $k+1$ eigenvectors of $T^\dagger T$,
$$\sigma_k(T)^2 \lVert x \rVert^2 \le
  \sum_i \lambda_i \lvert \langle e_i, x \rangle \rvert^2,$$
where $\lambda_i$ are the eigenvalues of $T^\dagger T$ and $e_i$ the corresponding
eigenbasis vectors. The proof expands $\lVert x \rVert^2$ via Parseval and applies
`termwise_eigenvalue_bound` coordinate-by-coordinate. -/
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
        (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E)) i) x‖^2 := by
  intro x hx
  have hpar : ‖x‖^2 = ∑ i, ‖inner 𝕜 ((T.isSymmetric_adjoint_comp_self.eigenvectorBasis
        (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E)) i) x‖^2 :=
    (OrthonormalBasis.sum_sq_norm_inner_right _ x).symm
  calc (T.singularValues k)^2 * ‖x‖^2
      = ∑ i, (T.singularValues k)^2 * ‖inner 𝕜
          ((T.isSymmetric_adjoint_comp_self.eigenvectorBasis
            (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E)) i) x‖^2 := by
        rw [hpar, Finset.mul_sum]
    _ ≤ ∑ i, (T.isSymmetric_adjoint_comp_self.eigenvalues
          (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E) i)
        * ‖inner 𝕜 ((T.isSymmetric_adjoint_comp_self.eigenvectorBasis
          (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E)) i) x‖^2 :=
        Finset.sum_le_sum fun i _ =>
          Library.LinearAlgebra.EckartYoung.SingularEigenRelations.termwise_eigenvalue_bound
            T k hk x hx i

/-- For every $x$ in the span of the first $k+1$ eigenvectors of $T^\dagger T$,
$$\sigma_k(T) \lVert x \rVert \le \lVert T x \rVert.$$
The proof proceeds by establishing the squared inequality
$\sigma_k(T)^2 \lVert x \rVert^2 \le \lVert T x \rVert^2$ via the eigenvalue
diagonalization of $T^\dagger T$ and `sum_eigen_lower_bound`, then extracting the
linear bound via `le_of_sq_le_sq`. -/
theorem norm_lower_bound_top_singular_span {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
    (T : E →ₗ[𝕜] F) (k : ℕ) (hk : k < Module.finrank 𝕜 E) :
    ∀ x ∈ Submodule.span 𝕜 (Set.range (fun i : Fin (k + 1) =>
      (T.isSymmetric_adjoint_comp_self.eigenvectorBasis
        (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E)) (Fin.castLE hk i))),
      T.singularValues k * ‖x‖ ≤ ‖T x‖ := by
  intro x hx
  -- ‖T x‖² = re⟪(T†∘T) x, x⟫
  have hTx : ‖T x‖ ^ 2 = RCLike.re (inner 𝕜 ((LinearMap.adjoint T ∘ₗ T) x) x) := by
    rw [LinearMap.comp_apply, LinearMap.adjoint_inner_left, inner_self_eq_norm_sq]
  -- diagonalization of the Gram operator in its eigenbasis
  have h_id : RCLike.re (inner 𝕜 ((LinearMap.adjoint T ∘ₗ T) x) x)
      = ∑ i : Fin (Module.finrank 𝕜 E),
          T.isSymmetric_adjoint_comp_self.eigenvalues rfl i
            * ‖inner 𝕜 (T.isSymmetric_adjoint_comp_self.eigenvectorBasis rfl i) x‖ ^ 2 :=
    re_inner_symm_eq_sum_eigenvalues (LinearMap.adjoint T ∘ₗ T)
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

/-- **Top singular subspace existence**: for every $k < \dim_{\mathbb{k}} E$ there exists
a $(k+1)$-dimensional subspace $V \le E$ such that
$\sigma_k(T) \lVert x \rVert \le \lVert T x \rVert$ for all $x \in V$.

The witness is the span of the first $k+1$ eigenvectors of the Gram operator
$T^\dagger T$, whose dimension is verified by `finrank_span_top_singular_eigenvectors`
and whose norm lower bound is `norm_lower_bound_top_singular_span`. -/
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

end Library.LinearAlgebra.EckartYoung.TopSingularSubspace
