import Mathlib

namespace Library.LinearAlgebra.PolarDecomposition.Basic

-- inner_diag_sum_eq_weighted: inner product of the diagonal-operator image against x equals
-- the weighted sum ∑ σ_i * ‖⟪b_E i, x⟫‖², by sum_inner + inner_smul_left + conj_mul.
-- entry_kind: Builder
theorem inner_diag_sum_eq_weighted {𝕜 : Type*} [RCLike 𝕜]
  {E : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
  (T : E →ₗ[𝕜] E)
  (b_E : OrthonormalBasis (Fin (Module.finrank 𝕜 E)) 𝕜 E)
  (x : E) :
  (inner 𝕜 (∑ i : Fin (Module.finrank 𝕜 E),
          (inner 𝕜 (b_E i) x : 𝕜) • (((T.singularValues (i : ℕ) : ℝ) : 𝕜) • b_E i)) x : 𝕜)
      = ∑ i : Fin (Module.finrank 𝕜 E),
          ((T.singularValues (i : ℕ) : ℝ) : 𝕜) * ((‖(inner 𝕜 (b_E i) x : 𝕜)‖^2 : ℝ) : 𝕜) := by
  simp_rw [sum_inner, smul_smul, inner_smul_left, map_mul, RCLike.conj_ofReal]
  congr 1; ext i
  have hconj := RCLike.conj_mul (inner 𝕜 (b_E i) x : 𝕜)
  calc (starRingEnd 𝕜) (inner 𝕜 (b_E i) x) * ↑(T.singularValues ↑i) * inner 𝕜 (b_E i) x
      = (starRingEnd 𝕜) (inner 𝕜 (b_E i) x) * inner 𝕜 (b_E i) x * ↑(T.singularValues ↑i) := by
        ring
    _ = ↑(T.singularValues ↑i) * ↑(‖(inner 𝕜 (b_E i) x : 𝕜)‖^2 : ℝ) := by
        rw [hconj]; push_cast; ring

-- entry_kind: Builder
-- p_constr_apply_eq_sum: Basis.constr on orthonormal basis expands via repr_apply_apply
-- (b_E.toBasis.constr 𝕜 f) x = ∑ i, ⟪b_E i, x⟫ • f i; simp fires the constr→repr→inner chain.
theorem p_constr_apply_eq_sum {𝕜 : Type*} [RCLike 𝕜]
  {E : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
  (T : E →ₗ[𝕜] E)
  (b_E : OrthonormalBasis (Fin (Module.finrank 𝕜 E)) 𝕜 E)
  (x : E) :
  (b_E.toBasis.constr 𝕜 (fun i => ((T.singularValues i : ℝ) : 𝕜) • b_E i)) x
      = ∑ i : Fin (Module.finrank 𝕜 E),
          (inner 𝕜 (b_E i) x : 𝕜) • (((T.singularValues (i : ℕ) : ℝ) : 𝕜) • b_E i) := by
  simp [OrthonormalBasis.repr_apply_apply]

-- entry_kind: Builder
theorem re_sum_weighted_eq_real_sum {𝕜 : Type*} [RCLike 𝕜]
  {E : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
  (T : E →ₗ[𝕜] E)
  (b_E : OrthonormalBasis (Fin (Module.finrank 𝕜 E)) 𝕜 E)
  (x : E) :
  RCLike.re (∑ i : Fin (Module.finrank 𝕜 E),
          ((T.singularValues (i : ℕ) : ℝ) : 𝕜) * ((‖(inner 𝕜 (b_E i) x : 𝕜)‖^2 : ℝ) : 𝕜))
      = ∑ i : Fin (Module.finrank 𝕜 E), T.singularValues (i : ℕ) * ‖(inner 𝕜 (b_E i) x : 𝕜)‖^2 := by norm_num

-- p_sum_sigma_norm_nonneg: sum of singularValues * ‖inner‖² is nonneg termwise
-- Each term is a product of two nonneg reals: singularValues_nonneg and sq_nonneg of a norm.
-- entry_kind: Builder
theorem p_sum_sigma_norm_nonneg {𝕜 : Type*} [RCLike 𝕜]
  {E : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
  (T : E →ₗ[𝕜] E)
  (b_E : OrthonormalBasis (Fin (Module.finrank 𝕜 E)) 𝕜 E)
  (x : E) :
  0 ≤ ∑ i : Fin (Module.finrank 𝕜 E), T.singularValues (i : ℕ) * ‖(inner 𝕜 (b_E i) x : 𝕜)‖^2 := by
  apply Finset.sum_nonneg
  intro i _
  apply mul_nonneg
  · exact T.singularValues_nonneg i
  · positivity

-- entry_kind: Builder
-- p_matrix_hermitian: the matrix of the diagonal operator b_E i ↦ σ_i • b_E i equals
-- Matrix.diagonal with real entries σ_i, which is Hermitian since real scalars are self-adjoint.
theorem p_matrix_hermitian {𝕜 : Type*} [RCLike 𝕜]
  {E : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
  (T : E →ₗ[𝕜] E)
  (b_E : OrthonormalBasis (Fin (Module.finrank 𝕜 E)) 𝕜 E) :
  ((b_E.toBasis.constr 𝕜 (fun i => ((T.singularValues i : ℝ) : 𝕜) • b_E i)).toMatrix
    b_E.toBasis b_E.toBasis).IsHermitian := by
  have hM : (b_E.toBasis.constr 𝕜 (fun i => ((T.singularValues i : ℝ) : 𝕜) • b_E i)).toMatrix
      b_E.toBasis b_E.toBasis =
      Matrix.diagonal (fun i : Fin (Module.finrank 𝕜 E) =>
        ((T.singularValues (i : ℕ) : ℝ) : 𝕜)) := by
    ext i j
    simp only [LinearMap.toMatrix_apply, OrthonormalBasis.coe_toBasis, Matrix.diagonal_apply]
    have hcb : ((b_E.toBasis.constr 𝕜) fun i => ((T.singularValues (i : ℕ) : ℝ) : 𝕜) • b_E i)
        (b_E j) = ((T.singularValues (j : ℕ) : ℝ) : 𝕜) • b_E j :=
      b_E.toBasis.constr_basis 𝕜 _ j
    rw [hcb, map_smul]
    rw [show b_E.toBasis.repr (b_E j) = Finsupp.single j 1 from by
      rw [← OrthonormalBasis.coe_toBasis]; exact b_E.toBasis.repr_self j]
    simp only [Finsupp.smul_apply, Finsupp.single_apply, smul_eq_mul, mul_ite,
               mul_one, mul_zero]
    simp only [eq_comm (a := j)]
    split_ifs with h
    · subst h; rfl
    · rfl
  rw [hM]
  apply Matrix.isHermitian_diagonal_iff.mpr
  intro i
  unfold IsSelfAdjoint
  simp [RCLike.star_def, RCLike.conj_ofReal]

-- entry_kind: Builder
theorem u_isometry : ∀ {𝕜 : Type*} [RCLike 𝕜]
  {E : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
  (b_E b_F : OrthonormalBasis (Fin (Module.finrank 𝕜 E)) 𝕜 E),
  ∀ x, ‖(b_E.equiv b_F (Equiv.refl _)).toLinearMap x‖ = ‖x‖ := by norm_num

-- Direct proof: two linear maps on E agree iff they agree on the basis b_E.
-- `Basis.ext` reduces to a pointwise check; `constr` sends b_E i ↦ σ_i • b_E i,
-- the isometry equiv sends that to σ_i • b_F i (equiv_apply_basis), and h_col
-- gives T (b_E i) = σ_i • b_F i. No sub-goals needed.
theorem t_factorization : ∀ {𝕜 : Type*} [RCLike 𝕜]
  {E : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
  (T : E →ₗ[𝕜] E)
  (b_E b_F : OrthonormalBasis (Fin (Module.finrank 𝕜 E)) 𝕜 E)
  (h_col : ∀ i, T (b_E i) = if h : (i : ℕ) < (Module.finrank 𝕜 E)
      then ((T.singularValues i : ℝ) : 𝕜) • b_F ⟨(i : ℕ), h⟩
      else 0),
  T = (b_E.equiv b_F (Equiv.refl _)).toLinearMap ∘ₗ
  b_E.toBasis.constr 𝕜 (fun i => ((T.singularValues i : ℝ) : 𝕜) • b_E i)  := by
  intro 𝕜 _ E _ _ _ T b_E b_F h_col
  apply b_E.toBasis.ext
  intro i
  simp only [OrthonormalBasis.coe_toBasis, LinearMap.comp_apply]
  rw [h_col i, dif_pos i.isLt]
  simp [OrthonormalBasis.equiv_apply_basis]

end Library.LinearAlgebra.PolarDecomposition.Basic
