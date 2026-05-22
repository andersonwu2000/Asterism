import Mathlib
import Problems.LinearAlgebra.svd.Defs
import Problems.LinearAlgebra.svd.proofs.L_normalized_t_orthonormal_on_supp

namespace Problems.LinearAlgebra.svd

-- Decompose into one orthonormality sub-goal: the family `j ↦ σ_{j.val}⁻¹ • T(b_E ⟨j.val,_⟩)`
-- (or junk on indices ≥ finrank E), restricted to indices where j.val < finrank E ∧ σ ≠ 0,
-- is orthonormal in F. Patch applies `Orthonormal.exists_orthonormalBasis_extension_of_card_eq`
-- to extend this orthonormal partial family to an `OrthonormalBasis (Fin (finrank F)) 𝕜 F`,
-- then identifies `b_F ⟨i,h⟩ = σ_i⁻¹ • T(b_E i)` for σ_i ≠ 0 and rearranges to the goal shape.
theorem s10859 : ∀ {𝕜 : Type*} [RCLike 𝕜]
  {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
  [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
  (T : E →ₗ[𝕜] F)
  (b_E : OrthonormalBasis (Fin (Module.finrank 𝕜 E)) 𝕜 E)
  (h_inner : ∀ i j, @inner 𝕜 _ _ (T (b_E i)) (T (b_E j)) =
    if i = j then (((T.singularValues i : ℝ)^2 : 𝕜)) else 0)
  (h_zero : ∀ (i : Fin (Module.finrank 𝕜 E)),
    ¬((i : ℕ) < Module.finrank 𝕜 F) → T (b_E i) = 0),
  ∃ (b_F : OrthonormalBasis (Fin (Module.finrank 𝕜 F)) 𝕜 F),
    ∀ (i : Fin (Module.finrank 𝕜 E)) (h : (i : ℕ) < Module.finrank 𝕜 F),
      (T.singularValues i : ℝ) ≠ 0 →
        T (b_E i) = ((T.singularValues i : ℝ) : 𝕜) • b_F ⟨(i : ℕ), h⟩  := by
  intro 𝕜 _ E F _ _ _ _ _ _ T b_E h_inner h_zero
  set v : Fin (Module.finrank 𝕜 F) → F := fun j =>
    if h : (j : ℕ) < Module.finrank 𝕜 E then
      ((T.singularValues (j : ℕ) : ℝ) : 𝕜)⁻¹ • T (b_E ⟨(j : ℕ), h⟩)
    else 0 with hv_def
  set s : Set (Fin (Module.finrank 𝕜 F)) :=
    {j | ((j : ℕ) < Module.finrank 𝕜 E) ∧ (T.singularValues (j : ℕ) : ℝ) ≠ 0} with hs_def
  have h_ortho : Orthonormal 𝕜 (Set.restrict s v) :=
    normalized_t_orthonormal_on_supp T b_E h_inner h_zero
  obtain ⟨b_F, hb_F⟩ := h_ortho.exists_orthonormalBasis_extension_of_card_eq
    (Fintype.card_fin _).symm
  refine ⟨b_F, fun i h hσ => ?_⟩
  have hi_in_s : (⟨(i : ℕ), h⟩ : Fin (Module.finrank 𝕜 F)) ∈ s := by
    refine ⟨i.isLt, hσ⟩
  have hbf_eq : b_F ⟨(i : ℕ), h⟩ = v ⟨(i : ℕ), h⟩ := hb_F _ hi_in_s
  simp only [hv_def, dif_pos i.isLt, Fin.eta] at hbf_eq
  have hσ_k : ((T.singularValues (i : ℕ) : ℝ) : 𝕜) ≠ 0 := by
    exact_mod_cast hσ
  rw [hbf_eq, smul_smul, mul_inv_cancel₀ hσ_k, one_smul]
end Problems.LinearAlgebra.svd
