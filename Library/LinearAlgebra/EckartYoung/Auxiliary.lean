import Mathlib

namespace Library.LinearAlgebra.EckartYoung.Auxiliary

-- opnorm_ge_of_vector_bound: lifts a pointwise bound c*‖x‖ ≤ ‖A x‖ to the operator norm c ≤ ‖A‖
-- Uses le_opNorm + coe_toContinuousLinearMap' to bridge linear/continuous application,
-- then divides by ‖x‖ > 0 via le_of_mul_le_mul_right.
theorem opnorm_ge_of_vector_bound {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F]
    (A : E →ₗ[𝕜] F) (x : E) (c : ℝ)
    (hx : x ≠ 0) (hbound : c * ‖x‖ ≤ ‖A x‖) :
    c ≤ ‖A.toContinuousLinearMap‖ := by
  have hxpos : 0 < ‖x‖ := norm_pos_iff.mpr hx
  have hle : ‖A x‖ ≤ ‖A.toContinuousLinearMap‖ * ‖x‖ := by
    have h := A.toContinuousLinearMap.le_opNorm x
    simp only [LinearMap.coe_toContinuousLinearMap'] at h
    exact h
  exact le_of_mul_le_mul_right (hbound.trans hle) hxpos

-- opnorm_ge_of_pointwise_bound: lifts a pointwise bound c*‖y‖ ≤ ‖A y‖ to the operator norm
-- via le_opNorm + coe_toContinuousLinearMap' bridge, then cancels ‖y‖ > 0.
theorem opnorm_ge_of_pointwise_bound {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
    (A : E →ₗ[𝕜] F) (y : E) (c : ℝ) (hy : y ≠ 0) (h : c * ‖y‖ ≤ ‖A y‖) :
    c ≤ ‖A.toContinuousLinearMap‖ := by
  have hle : ‖A y‖ ≤ ‖A.toContinuousLinearMap‖ * ‖y‖ := by
    have := A.toContinuousLinearMap.le_opNorm y
    simp only [LinearMap.coe_toContinuousLinearMap'] at this
    exact this
  exact le_of_mul_le_mul_right (h.trans hle) (norm_pos_iff.mpr hy)

-- exists_nonzero_mem_inf_of_finrank: dimension-count intersection over a general field
-- If dim U + dim W > dim V, then U ⊓ W contains a nonzero vector.
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

theorem exists_nonzero_mem_inf_of_finrank_2 {K : Type*} [Field K]
    {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
    (U W : Submodule K V)
    (h : Module.finrank K V < Module.finrank K U + Module.finrank K W) :
    ∃ x : V, x ∈ U ∧ x ∈ W ∧ x ≠ 0 := by apply exists_nonzero_mem_inf_of_finrank <;> assumption

-- ker_finrank_ge: rank–nullity bounds finrank E by finrank (ker S) + k when range S has rank ≤ k
theorem ker_finrank_ge {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
    (S : E →ₗ[𝕜] F) (k : ℕ)
    (hrank : Module.finrank 𝕜 (LinearMap.range S) ≤ k) :
    Module.finrank 𝕜 E ≤ Module.finrank 𝕜 (LinearMap.ker S) + k := by
  have h := S.finrank_range_add_finrank_ker (K := 𝕜)
  omega

-- norm_sub_starprojection_le: orthogonal complement contraction — ‖x − Kx‖ ≤ ‖x‖ via Pythagoras
-- Uses orthogonalProjectionFn_norm_sq (Pythagorean identity) to bound the orthogonal residual.
theorem norm_sub_starprojection_le {𝕜 : Type*} [RCLike 𝕜]
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    (K : Submodule 𝕜 E) (x : E) :
    ‖x - K.starProjection x‖ ≤ ‖x‖ := by
  have hpy := K.orthogonalProjectionFn_norm_sq x
  simp only [Submodule.orthogonalProjectionFn_eq, Submodule.coe_orthogonalProjection_apply] at hpy
  nlinarith [norm_nonneg x, norm_nonneg (x - K.starProjection x), norm_nonneg (K.starProjection x)]

end Library.LinearAlgebra.EckartYoung.Auxiliary
