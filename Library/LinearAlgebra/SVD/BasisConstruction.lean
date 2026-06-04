import Library.LinearAlgebra.SVD.SingularValues
import Mathlib

open Library.LinearAlgebra.SVD.SingularValues

namespace Library.LinearAlgebra.SVD.BasisConstruction

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

-- entry_kind: Builder
-- inner_t_eigenbasis_sq_diag: ⟨T(b_E i), T(b_E j)⟩ = σ_i² δ_ij via adjoint rewrite + orthonormality
theorem inner_t_eigenbasis_sq_diag : ∀ {𝕜 : Type*} [RCLike 𝕜]
  {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
  [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
  (T : E →ₗ[𝕜] F)
  (b_E : OrthonormalBasis (Fin (Module.finrank 𝕜 E)) 𝕜 E)
  (h_eig : ∀ i, (T.adjoint ∘ₗ T) (b_E i) =
      (((T.singularValues i : ℝ)^2 : 𝕜)) • b_E i),
  ∀ i j, @inner 𝕜 _ _ (T (b_E i)) (T (b_E j)) =
    if i = j then (((T.singularValues i : ℝ)^2 : 𝕜)) else 0 := by
  intro 𝕜 _ E F _ _ _ _ _ _ T b_E h_eig i j
  simp only [LinearMap.comp_apply] at h_eig
  rw [← LinearMap.adjoint_inner_left, h_eig i, inner_smul_left]
  have hconj : starRingEnd 𝕜 (((T.singularValues i : ℝ)^2 : 𝕜)) =
      (((T.singularValues i : ℝ)^2 : 𝕜)) := by
    simp [RCLike.conj_ofReal]
  rw [hconj]
  have horth := orthonormal_iff_ite.mp b_E.orthonormal i j
  split_ifs with h
  · subst h
    simp
  · simp [horth, if_neg h]

-- Decompose into one orthonormality sub-goal: the family `j ↦ σ_{j.val}⁻¹ • T(b_E ⟨j.val,_⟩)`
-- (or junk on indices ≥ finrank E), restricted to indices where j.val < finrank E ∧ σ ≠ 0,
-- is orthonormal in F. Patch applies `Orthonormal.exists_orthonormalBasis_extension_of_card_eq`
-- to extend this orthonormal partial family to an `OrthonormalBasis (Fin (finrank F)) 𝕜 F`,
-- then identifies `b_F ⟨i,h⟩ = σ_i⁻¹ • T(b_E i)` for σ_i ≠ 0 and rearranges to the goal shape.
theorem exists_b_f_apply_eq_nonzero : ∀ {𝕜 : Type*} [RCLike 𝕜]
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

-- Split into two siblings:
--   (A) `t_b_e_zero_of_sigma_zero` (Builder): σ_i = 0 ⇒ T(b_E i) = 0, from h_inner with j=i.
--   (B) `exists_b_f_apply_eq_nonzero` (Backward): orthonormal-extension construction,
--       restricted to the apply equation when σ_i ≠ 0.
-- Closer fuses (A)+(B): low-index branch splits on σ_i; σ_i=0 makes both sides 0 via (A),
-- σ_i≠0 uses (B); high-index branch uses h_zero via `dif_neg`.
theorem exists_b_f_apply_eq_dite_with_zero : ∀ {𝕜 : Type*} [RCLike 𝕜]
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

-- entry_kind: Builder
-- sum_ite_smul_eq_dite: collapse indicator-shaped Finset.sum to dite by Finset.sum_eq_single
theorem sum_ite_smul_eq_dite : ∀ {𝕜 : Type*} [RCLike 𝕜]
  {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
  [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
  (T : E →ₗ[𝕜] F)
  (b_E : OrthonormalBasis (Fin (Module.finrank 𝕜 E)) 𝕜 E)
  (h_inner : ∀ i j, @inner 𝕜 _ _ (T (b_E i)) (T (b_E j)) =
    if i = j then (((T.singularValues i : ℝ)^2 : 𝕜)) else 0)
  (b_F : OrthonormalBasis (Fin (Module.finrank 𝕜 F)) 𝕜 F)
  (i : Fin (Module.finrank 𝕜 E)),
    (∑ j : Fin (Module.finrank 𝕜 F),
      (if (j : ℕ) = (i : ℕ) then ((T.singularValues i : ℝ) : 𝕜) else 0) • b_F j) =
    if h : (i : ℕ) < (Module.finrank 𝕜 F)
    then ((T.singularValues i : ℝ) : 𝕜) • b_F ⟨(i : ℕ), h⟩
    else 0 := by
  intro 𝕜 _ E F _ _ _ _ _ _ T b_E h_inner b_F i
  split_ifs with h
  · rw [Finset.sum_eq_single ⟨(i : ℕ), h⟩]
    · simp
    · intro j _ hj
      have hne : (j : ℕ) ≠ (i : ℕ) := fun heq => hj (Fin.ext heq)
      simp [hne]
    · intro hmem
      exact absurd (Finset.mem_univ _) hmem
  · apply Finset.sum_eq_zero
    intro j _
    have hne : (j : ℕ) ≠ (i : ℕ) :=
      Nat.ne_of_lt (j.isLt.trans_le (Nat.le_of_not_lt h))
    simp [hne]

-- Split into (A) `t_apply_eigenbasis_zero_high`: T(b_E i) = 0 for indices
-- i with (i:ℕ) ≥ finrank F, derived from h_inner (giving ‖T(b_E i)‖² = σ_i²)
-- combined with the rank ≤ codimension bound forcing σ_i = 0 there, and
-- (B) `exists_b_f_apply_eq_dite_with_zero`: the main b_F existence assuming
-- that zero fact as a hypothesis. (A) is a single-equation kernel fact;
-- (B) absorbs all orthonormal-extension construction work and merely uses
-- the zero hypothesis to close the dite "else" branch directly.
theorem b_f_apply_eq_dite : ∀ {𝕜 : Type*} [RCLike 𝕜]
  {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
  [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
  (T : E →ₗ[𝕜] F)
  (b_E : OrthonormalBasis (Fin (Module.finrank 𝕜 E)) 𝕜 E)
  (h_inner : ∀ i j, @inner 𝕜 _ _ (T (b_E i)) (T (b_E j)) =
    if i = j then (((T.singularValues i : ℝ)^2 : 𝕜)) else 0),
  ∃ (b_F : OrthonormalBasis (Fin (Module.finrank 𝕜 F)) 𝕜 F),
    ∀ i, T (b_E i) =
      if h : (i : ℕ) < (Module.finrank 𝕜 F)
      then ((T.singularValues i : ℝ) : 𝕜) • b_F ⟨(i : ℕ), h⟩
      else 0  := by
  intro 𝕜 _ E F _ _ _ _ _ _ T b_E h_inner
  have h_zero := t_apply_eigenbasis_zero_high T b_E h_inner
  exact exists_b_f_apply_eq_dite_with_zero T b_E h_inner h_zero

-- Decompose into (A) constructing b_F : OrthonormalBasis of F packaging the
-- orthonormal-extension construction, with per-index dite-form column property
-- (T(b_E i) = σ_i • b_F⟨i,_⟩ when (i:ℕ) < finrank F, else 0), and (B) a purely
-- algebraic identity collapsing the indicator-shaped sum to that dite. (A) absorbs
-- all geometric/construction work; (B) is T,b_E,h_inner-independent Finset.sum
-- manipulation. Combinator rewrites the parent sum via (B), then closes by (A).
theorem exists_b_f_apply_eq : ∀ {𝕜 : Type*} [RCLike 𝕜]
  {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
  [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
  (T : E →ₗ[𝕜] F)
  (b_E : OrthonormalBasis (Fin (Module.finrank 𝕜 E)) 𝕜 E)
  (h_inner : ∀ i j, @inner 𝕜 _ _ (T (b_E i)) (T (b_E j)) =
    if i = j then (((T.singularValues i : ℝ)^2 : 𝕜)) else 0),
  ∃ (b_F : OrthonormalBasis (Fin (Module.finrank 𝕜 F)) 𝕜 F),
    ∀ i, T (b_E i) = ∑ j : Fin (Module.finrank 𝕜 F),
      (if (j : ℕ) = (i : ℕ) then ((T.singularValues i : ℝ) : 𝕜) else 0) • b_F j := by
  intro 𝕜 _ E F _ _ _ _ _ _ T b_E h_inner
  obtain ⟨b_F, h_col⟩ := b_f_apply_eq_dite T b_E h_inner
  refine ⟨b_F, fun i => ?_⟩
  rw [sum_ite_smul_eq_dite T b_E h_inner b_F i]
  exact h_col i

end Library.LinearAlgebra.SVD.BasisConstruction
