import Mathlib.Analysis.InnerProductSpace.Orthogonal
import Mathlib.Analysis.InnerProductSpace.SingularValues

/-!
# Singular value–eigenvalue relations for linear maps

This file establishes termwise inequalities between the singular values $\sigma_k$ of a
linear map `T : E →ₗ[𝕜] F` and the eigenvalues of the self-adjoint operator `T† ∘ T`,
as needed in the proof of the Eckart–Young theorem.

## Main statements

* `sq_singular_k_le_eigenvalue` — $\sigma_k^2 \leq \lambda_i$ for $i \leq k$, using the
  antitone ordering of singular values and `LinearMap.sq_singularValues_fin`.
* `inner_eigenvector_high_eq_zero` — for $x$ in the span of the first $k+1$ eigenvectors,
  $\langle b_i, x\rangle = 0$ whenever $i > k$.
* `termwise_eigenvalue_bound` — per-coordinate bound
  $\sigma_k^2 \|\langle b_i, x\rangle\|^2 \leq \lambda_i \|\langle b_i, x\rangle\|^2$
  for $x$ in the span of the first $k+1$ eigenvectors.
* `eigenvalues_le_sq_singularValues` — $\lambda_i \leq \sigma_k^2$ for $i \geq k$.
* `inner_eigenvectorBasis_eq_zero_of_mem_orthogonal` — for $y$ in the orthogonal complement
  of the span of the first $k$ eigenvectors, $\langle b_i, y\rangle = 0$ when $i < k$.
* `termwise_le_singular_k` — reverse per-coordinate bound on the orthogonal complement.

## Implementation notes

All results work over any `RCLike` scalar field `𝕜` and finite-dimensional inner product
spaces `E` and `F`.
-/

namespace Library.LinearAlgebra.EckartYoung.SingularEigenRelations

/-- For $i \leq k$, the square of the $k$-th singular value of `T` is at most the $i$-th
eigenvalue of `T† ∘ T`. This follows from the antitone ordering of singular values
together with `LinearMap.sq_singularValues_fin`. -/
theorem sq_singular_k_le_eigenvalue {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
    (T : E →ₗ[𝕜] F) (k : ℕ) (_hk : k < Module.finrank 𝕜 E)
    (i : Fin (Module.finrank 𝕜 E)) (hik : (i : ℕ) ≤ k) :
    T.singularValues k ^ 2
      ≤ T.isSymmetric_adjoint_comp_self.eigenvalues rfl i := by
  calc T.singularValues k ^ 2
      ≤ T.singularValues i ^ 2 := by
        apply pow_le_pow_left₀ (T.singularValues_nonneg k)
        exact T.singularValues_antitone hik
    _ = T.isSymmetric_adjoint_comp_self.eigenvalues rfl i := T.sq_singularValues_fin rfl i

/-- The $i$-th eigenvector `b i` (with $i > k$) is orthogonal to the span of the first
$k+1$ eigenvectors. Precisely: for `x` in
`span {b (castLE j) | j : Fin (k + 1)}` and `k < i`, we have $\langle b_i, x\rangle = 0$.

The proof proceeds by `Submodule.span_induction`: orthogonality on generators follows from
`b.orthonormal.2` (indices are distinct since `castLE j ≤ k < i`), and is preserved under
addition and scalar multiplication via `inner_add_right`/`inner_smul_right`. -/
theorem inner_eigenvector_high_eq_zero {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
    (T : E →ₗ[𝕜] F) (k : ℕ) (hk : k < Module.finrank 𝕜 E)
    (x : E) (hx : x ∈ Submodule.span 𝕜 (Set.range (fun i : Fin (k + 1) =>
      (T.isSymmetric_adjoint_comp_self.eigenvectorBasis
        (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E)) (Fin.castLE hk i))))
    (i : Fin (Module.finrank 𝕜 E)) (hik : k < (i : ℕ)) :
    inner 𝕜 (T.isSymmetric_adjoint_comp_self.eigenvectorBasis rfl i) x = (0 : 𝕜) := by
  set b := T.isSymmetric_adjoint_comp_self.eigenvectorBasis rfl with hb
  have horth : b i ∈ (Submodule.span 𝕜 (Set.range (fun j : Fin (k + 1) =>
      b (Fin.castLE hk j))))ᗮ := by
    rw [Submodule.mem_orthogonal']
    intro u hu
    induction hu using Submodule.span_induction with
    | mem y hy =>
        obtain ⟨j, rfl⟩ := hy
        have hne : i ≠ Fin.castLE hk j := by
          intro h
          have hv := congrArg Fin.val h
          simp only [Fin.val_castLE] at hv
          have hj := j.isLt
          omega
        exact b.orthonormal.2 hne
    | zero => simp
    | add y z _ _ hy hz => rw [inner_add_right, hy, hz, add_zero]
    | smul c y _ hy => rw [inner_smul_right, hy, mul_zero]
  exact Submodule.inner_left_of_mem_orthogonal hx horth

/-- Per-coordinate spectral bound: for `x` in the span of the first $k+1$ eigenvectors
and any index `i`, we have
$\sigma_k^2 \|\langle b_i, x\rangle\|^2 \leq \lambda_i \|\langle b_i, x\rangle\|^2$.

* If $i \leq k$: apply `sq_singular_k_le_eigenvalue` and scale by
  $\|\langle b_i, x\rangle\|^2 \geq 0$.
* If $i > k$: $\langle b_i, x\rangle = 0$ by `inner_eigenvector_high_eq_zero`,
  so both sides vanish. -/
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
        * ‖inner 𝕜 (T.isSymmetric_adjoint_comp_self.eigenvectorBasis rfl i) x‖ ^ 2 := by
  by_cases hik : (i : ℕ) ≤ k
  · have h_eig := sq_singular_k_le_eigenvalue T k hk i hik
    exact mul_le_mul_of_nonneg_right h_eig (sq_nonneg _)
  · have h_orth := inner_eigenvector_high_eq_zero T k hk x hx i (not_le.mp hik)
    rw [h_orth]; simp

/-- For $i \geq k$, the $i$-th eigenvalue of `T† ∘ T` is at most $\sigma_k^2$, using
`LinearMap.sq_singularValues_fin` and the antitone ordering of singular values. -/
theorem eigenvalues_le_sq_singularValues {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
    (T : E →ₗ[𝕜] F) (k : ℕ) (_hk : k < Module.finrank 𝕜 E)
    (i : Fin (Module.finrank 𝕜 E)) (h : k ≤ (i : ℕ)) :
    T.isSymmetric_adjoint_comp_self.eigenvalues
        (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E) i ≤ (T.singularValues k) ^ 2 := by
  calc T.isSymmetric_adjoint_comp_self.eigenvalues
          (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E) i
      = T.singularValues ↑i ^ 2 := (T.sq_singularValues_fin rfl i).symm
    _ ≤ (T.singularValues k) ^ 2 :=
        pow_le_pow_left₀ (T.singularValues_nonneg ↑i) (T.singularValues_antitone h) 2

/-- The $i$-th eigenvector `b i` lies in the span $K$ of the first $k$ eigenvectors, so
for any $y \in K^\perp$ with $i < k$ we have $\langle b_i, y\rangle = 0$. -/
theorem inner_eigenvectorBasis_eq_zero_of_mem_orthogonal {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
    (T : E →ₗ[𝕜] F) (k : ℕ) (hk : k < Module.finrank 𝕜 E)
    (y : E) (hy : y ∈ (Submodule.span 𝕜 (Set.range (fun i : Fin k =>
      (T.isSymmetric_adjoint_comp_self.eigenvectorBasis
        (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E)) (Fin.castLE hk.le i))))ᗮ)
    (i : Fin (Module.finrank 𝕜 E)) (h : (i : ℕ) < k) :
    inner 𝕜 ((T.isSymmetric_adjoint_comp_self.eigenvectorBasis
        (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E)) i) y = 0 := by
  have hb : (T.isSymmetric_adjoint_comp_self.eigenvectorBasis rfl i) ∈
      Submodule.span 𝕜 (Set.range (fun j : Fin k =>
        (T.isSymmetric_adjoint_comp_self.eigenvectorBasis rfl) (Fin.castLE hk.le j))) := by
    apply Submodule.subset_span
    exact ⟨⟨(i : ℕ), h⟩, by congr 1⟩
  exact (Submodule.mem_orthogonal _ _).mp hy _ hb

/-- Reverse per-coordinate bound on the orthogonal complement: for `y ∈ Kᗮ` (the orthogonal
complement of the span $K$ of the first $k$ eigenvectors) and any index `i`,
$\lambda_i \|\langle b_i, y\rangle\|^2 \leq \sigma_k^2 \|\langle b_i, y\rangle\|^2$.

* If $i \geq k$: apply `eigenvalues_le_sq_singularValues` and scale by
  $\|\langle b_i, y\rangle\|^2 \geq 0$.
* If $i < k$: `b i` lies in $K$, so $\langle b_i, y\rangle = 0$ by
  `inner_eigenvectorBasis_eq_zero_of_mem_orthogonal`; both sides vanish. -/
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
            (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E)) i) y‖ ^ 2 := by
  by_cases h : k ≤ (i : ℕ)
  · have h_eig := eigenvalues_le_sq_singularValues T k hk i h
    exact mul_le_mul_of_nonneg_right h_eig (sq_nonneg _)
  · have h_orth := inner_eigenvectorBasis_eq_zero_of_mem_orthogonal T k hk y hy i (not_le.mp h)
    rw [h_orth]
    simp

end Library.LinearAlgebra.EckartYoung.SingularEigenRelations
