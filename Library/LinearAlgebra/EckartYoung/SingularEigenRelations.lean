import Mathlib

namespace Library.LinearAlgebra.EckartYoung.SingularEigenRelations

-- sq_singular_k_le_eigenvalue: σ_k² ≤ λ_i for i ≤ k,
-- via antitone singular values + sq_singularValues_fin
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

-- eigen_ge_low: σ_k² ≤ λ_i for i ≤ k, using sq_singularValues_fin + eigenvalues_antitone
theorem eigen_ge_low {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
    (T : E →ₗ[𝕜] F) (k : ℕ) (hk : k < Module.finrank 𝕜 E)
    (i : Fin (Module.finrank 𝕜 E)) (hi : (i : ℕ) ≤ k) :
    (T.singularValues k)^2 ≤ T.isSymmetric_adjoint_comp_self.eigenvalues
      (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E) i := by
  rw [T.sq_singularValues_fin rfl ⟨k, hk⟩]
  exact T.isSymmetric_adjoint_comp_self.eigenvalues_antitone rfl hi

-- eig_le_sigma_sq: k-th eigenvalue of T†T is ≤ (σ_k)² using sq_singularValues_fin + antitone
theorem eig_le_sigma_sq {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
    (T : E →ₗ[𝕜] F) (k : ℕ) (hk : k < Module.finrank 𝕜 E)
    (i : Fin (Module.finrank 𝕜 E)) (h : k ≤ (i : ℕ)) :
    T.isSymmetric_adjoint_comp_self.eigenvalues
        (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E) i ≤ (T.singularValues k) ^ 2 := by
  calc T.isSymmetric_adjoint_comp_self.eigenvalues
          (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E) i
      = T.singularValues ↑i ^ 2 := (T.sq_singularValues_fin rfl i).symm
    _ ≤ (T.singularValues k) ^ 2 :=
        pow_le_pow_left₀ (T.singularValues_nonneg ↑i) (T.singularValues_antitone h) 2

-- Direct leaf: `b i` (high eigenvector, `i > k`) is orthogonal to the top-(k+1) span.
-- Show `b i ∈ (span {b (castLE j)})ᗮ` by span-induction: on generators it is the
-- orthonormality of the eigenbasis (`b.orthonormal.2`, indices distinct since `castLE j ≤ k < i`),
-- closed under `+`/`•` via `inner_add_right`/`inner_smul_right`; then `inner_left_of_mem_orthogonal hx`.
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

-- Direct leaf: x is a finite combination of the first k+1 eigenvectors b(castLE j),
-- and b i (with i > k) is orthogonal to each of them, so ⟨b i, x⟩ vanishes termwise.
-- Expand x via mem_span_range_iff_exists_fun, push inner through the sum/scalar,
-- and kill each ⟨b i, b (castLE j)⟩ by orthonormality since i ≠ castLE j (val j ≤ k < i).
theorem inner_zero_high {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
    (T : E →ₗ[𝕜] F) (k : ℕ) (hk : k < Module.finrank 𝕜 E)
    (x : E) (hx : x ∈ Submodule.span 𝕜 (Set.range (fun i : Fin (k + 1) =>
      (T.isSymmetric_adjoint_comp_self.eigenvectorBasis
        (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E)) (Fin.castLE hk i))))
    (i : Fin (Module.finrank 𝕜 E)) (hi : k < (i : ℕ)) :
    (inner 𝕜 ((T.isSymmetric_adjoint_comp_self.eigenvectorBasis
      (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E)) i) x : 𝕜) = 0  := by
  set b := T.isSymmetric_adjoint_comp_self.eigenvectorBasis
    (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E) with hb
  obtain ⟨c, rfl⟩ := (Submodule.mem_span_range_iff_exists_fun 𝕜).mp hx
  rw [inner_sum]
  apply Finset.sum_eq_zero
  intro j _
  rw [inner_smul_right]
  have hij : i ≠ Fin.castLE hk j := by
    apply Fin.ne_of_val_ne
    simp only [Fin.val_castLE]
    omega
  rw [b.orthonormal.2 hij, mul_zero]

-- inner_eigvec_orthogonal: eigenvector bᵢ (i < k) is orthogonal to Kᗮ via Submodule.mem_orthogonal
-- bᵢ lies in the span K of the first k eigenvectors; y ∈ Kᗮ implies ⟪bᵢ, y⟫ = 0.
theorem inner_eigvec_orthogonal {𝕜 : Type*} [RCLike 𝕜]
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

end Library.LinearAlgebra.EckartYoung.SingularEigenRelations
