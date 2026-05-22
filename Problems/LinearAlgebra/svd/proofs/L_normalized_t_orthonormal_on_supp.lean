import Mathlib
import Problems.LinearAlgebra.svd.Defs

namespace Problems.LinearAlgebra.svd

-- normalized_t_orthonormal_on_supp: orthonormal_iff_ite + inner_smul factoring closes the goal;
-- diagonal inner products equal 1 via field_simp with RCLike.ofReal_ne_zero; off-diagonal are 0.
-- entry_kind: Builder
theorem normalized_t_orthonormal_on_supp : ∀ {𝕜 : Type*} [RCLike 𝕜]
  {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
  [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
  (T : E →ₗ[𝕜] F)
  (b_E : OrthonormalBasis (Fin (Module.finrank 𝕜 E)) 𝕜 E)
  (h_inner : ∀ i j, @inner 𝕜 _ _ (T (b_E i)) (T (b_E j)) =
    if i = j then (((T.singularValues i : ℝ)^2 : 𝕜)) else 0)
  (h_zero : ∀ (i : Fin (Module.finrank 𝕜 E)),
    ¬((i : ℕ) < Module.finrank 𝕜 F) → T (b_E i) = 0),
  Orthonormal 𝕜
    (Set.restrict
      ({j : Fin (Module.finrank 𝕜 F) |
          ((j : ℕ) < Module.finrank 𝕜 E) ∧ (T.singularValues (j : ℕ) : ℝ) ≠ 0})
      (fun j : Fin (Module.finrank 𝕜 F) =>
        if h : (j : ℕ) < Module.finrank 𝕜 E then
          ((T.singularValues (j : ℕ) : ℝ) : 𝕜)⁻¹ • T (b_E ⟨(j : ℕ), h⟩)
        else (0 : F))) := by
  intro 𝕜 _ E F _ _ _ _ _ _ T b_E h_inner h_zero
  rw [orthonormal_iff_ite]
  rintro ⟨j, hj⟩ ⟨k, hk⟩
  obtain ⟨hj_lt, hj_nz⟩ := hj
  obtain ⟨hk_lt, hk_nz⟩ := hk
  simp only [Set.restrict_apply, dif_pos hj_lt, dif_pos hk_lt]
  rw [inner_smul_left, inner_smul_right]
  have hij := h_inner ⟨j.val, hj_lt⟩ ⟨k.val, hk_lt⟩
  rw [hij]
  have hjeqk : (⟨j.val, hj_lt⟩ : Fin _) = ⟨k.val, hk_lt⟩ ↔ j = k := by
    simp [Fin.ext_iff]
  simp only [hjeqk]
  by_cases hjk : j = k
  · subst hjk
    simp only [ite_true, map_inv₀]
    rw [RCLike.conj_ofReal]
    field_simp [RCLike.ofReal_ne_zero.mpr hj_nz]
  · simp [hjk]
end Problems.LinearAlgebra.svd