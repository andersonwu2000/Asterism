import Mathlib

namespace Library.LinearAlgebra.EckartYoung.EigenExpansion

-- Spectral diagonalization of the Rayleigh form for a symmetric operator.
-- Expand ⟪T x, x⟫ over the eigenbasis via `sum_inner_mul_inner`; per term use
-- symmetry `⟪T x, bᵢ⟫ = ⟪x, T bᵢ⟫`, `T bᵢ = μᵢ • bᵢ`, and `conj z * z = ‖z‖²`,
-- then `re ∘ ofReal` collapses each real summand. Direct (no sub-goals).
theorem re_inner_symm_eq_sum_eigenvalues {𝕜 : Type*} [RCLike 𝕜] {E : Type*}
    [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    (T : E →ₗ[𝕜] E) (hT : T.IsSymmetric) {n : ℕ} (hn : Module.finrank 𝕜 E = n) (x : E) :
    RCLike.re (inner 𝕜 (T x) x)
      = ∑ i : Fin n, hT.eigenvalues hn i * ‖inner 𝕜 (hT.eigenvectorBasis hn i) x‖ ^ 2  := by
  classical
  rw [← OrthonormalBasis.sum_inner_mul_inner (hT.eigenvectorBasis hn) (T x) x, map_sum]
  apply Finset.sum_congr rfl
  intro i _
  rw [hT x (hT.eigenvectorBasis hn i), hT.apply_eigenvectorBasis hn i, inner_smul_right,
      ← inner_conj_symm, mul_assoc, RCLike.conj_mul,
      ← RCLike.ofReal_pow, ← RCLike.ofReal_mul, RCLike.ofReal_re]

theorem re_inner_symm_eq_sum_eigenvalues_2 {𝕜 : Type*} [RCLike 𝕜] {E : Type*}
    [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    (T : E →ₗ[𝕜] E) (hT : T.IsSymmetric) {n : ℕ} (hn : Module.finrank 𝕜 E = n) (x : E) :
    RCLike.re (inner 𝕜 (T x) x)
      = ∑ i : Fin n, hT.eigenvalues hn i * ‖inner 𝕜 (hT.eigenvectorBasis hn i) x‖ ^ 2 := by apply re_inner_symm_eq_sum_eigenvalues <;> assumption

-- norm_sq_eq_sum_eigen: ‖Tx‖² = ∑ λᵢ‖⟨bᵢ,x⟩‖² where (b,λ) = eigenbasis/eigvals of T†T.
-- Reduce ‖Tx‖² = re⟪T†T x,x⟫ via norm_sq_eq_re_inner + adjoint_inner_left,
-- then expand with sum_inner_mul_inner and collapse each term via hA-symmetry + conj_mul.
theorem norm_sq_eq_sum_eigen {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
    (T : E →ₗ[𝕜] F) (x : E) :
    ‖T x‖^2 = ∑ i, (T.isSymmetric_adjoint_comp_self.eigenvalues
        (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E) i)
      * ‖inner 𝕜 ((T.isSymmetric_adjoint_comp_self.eigenvectorBasis
        (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E)) i) x‖^2 := by
  set hA := T.isSymmetric_adjoint_comp_self
  rw [norm_sq_eq_re_inner (𝕜 := 𝕜), ← LinearMap.adjoint_inner_left]
  simp only [← LinearMap.comp_apply]
  classical
  rw [← OrthonormalBasis.sum_inner_mul_inner (hA.eigenvectorBasis rfl) ((T.adjoint ∘ₗ T) x) x,
      map_sum]
  apply Finset.sum_congr rfl
  intro i _
  rw [hA x (hA.eigenvectorBasis rfl i), hA.apply_eigenvectorBasis rfl i, inner_smul_right,
      ← inner_conj_symm, mul_assoc, RCLike.conj_mul,
      ← RCLike.ofReal_pow, ← RCLike.ofReal_mul, RCLike.ofReal_re]

theorem norm_sq_eq_sum_eigen_2 {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
    (T : E →ₗ[𝕜] F) (x : E) :
    ‖T x‖^2 = ∑ i, (T.isSymmetric_adjoint_comp_self.eigenvalues
        (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E) i)
      * ‖inner 𝕜 ((T.isSymmetric_adjoint_comp_self.eigenvectorBasis
        (rfl : Module.finrank 𝕜 E = Module.finrank 𝕜 E)) i) x‖^2 := by apply norm_sq_eq_sum_eigen <;> assumption

end Library.LinearAlgebra.EckartYoung.EigenExpansion
