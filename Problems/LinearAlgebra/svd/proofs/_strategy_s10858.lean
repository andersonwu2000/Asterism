import Mathlib
import Problems.LinearAlgebra.svd.Defs
import Problems.LinearAlgebra.svd.proofs.L_exists_b_f_apply_eq_nonzero
import Problems.LinearAlgebra.svd.proofs.L_t_b_e_zero_of_sigma_zero

namespace Problems.LinearAlgebra.svd

-- Split into two siblings:
--   (A) `t_b_e_zero_of_sigma_zero` (Builder): σ_i = 0 ⇒ T(b_E i) = 0, from h_inner with j=i.
--   (B) `exists_b_f_apply_eq_nonzero` (Backward): orthonormal-extension construction,
--       restricted to the apply equation when σ_i ≠ 0.
-- Closer fuses (A)+(B): low-index branch splits on σ_i; σ_i=0 makes both sides 0 via (A),
-- σ_i≠0 uses (B); high-index branch uses h_zero via `dif_neg`.
theorem s10858 : ∀ {𝕜 : Type*} [RCLike 𝕜]
  {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
  [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
  (T : E →ₗ[𝕜] F)
  (b_E : OrthonormalBasis (Fin (Module.finrank 𝕜 E)) 𝕜 E)
  (h_inner : ∀ i j, @inner 𝕜 _ _ (T (b_E i)) (T (b_E j)) =
    if i = j then (((T.singularValues i : ℝ)^2 : 𝕜)) else 0)
  (h_zero : ∀ (i : Fin (Module.finrank 𝕜 E)),
    ¬((i : ℕ) < Module.finrank 𝕜 F) → T (b_E i) = 0),
  ∃ (b_F : OrthonormalBasis (Fin (Module.finrank 𝕜 F)) 𝕜 F),
    ∀ i, T (b_E i) =
      if h : (i : ℕ) < (Module.finrank 𝕜 F)
      then ((T.singularValues i : ℝ) : 𝕜) • b_F ⟨(i : ℕ), h⟩
      else 0  := by
  intro 𝕜 _ E F _ _ _ _ _ _ T b_E h_inner h_zero
  have h_sigma_zero := t_b_e_zero_of_sigma_zero T b_E h_inner h_zero
  have h_main := exists_b_f_apply_eq_nonzero T b_E h_inner h_zero
  obtain ⟨b_F, h_low⟩ := h_main
  refine ⟨b_F, fun i => ?_⟩
  by_cases h : (i : ℕ) < Module.finrank 𝕜 F
  · rw [dif_pos h]
    by_cases hσ : (T.singularValues i : ℝ) = 0
    · rw [h_sigma_zero i hσ, hσ]; simp
    · exact h_low i h hσ
  · rw [dif_neg h]; exact h_zero i h

end Problems.LinearAlgebra.svd
