import Library.LinearAlgebra.SVD.SingularValues
import Mathlib.Algebra.BigOperators.Group.Finset.Basic
import Mathlib.Analysis.InnerProductSpace.Adjoint
import Mathlib.Analysis.InnerProductSpace.SingularValues
import Mathlib.Data.Fin.Basic
import Mathlib.Data.Set.Function

open Library.LinearAlgebra.SVD.SingularValues

/-!
# Basis Construction for the SVD

This file constructs an orthonormal basis `b_F` of the codomain `F` from a given orthonormal
basis `b_E` of the domain `E`, compatible with the singular value decomposition of a linear map
`T : E →ₗ[𝕜] F` between finite-dimensional inner product spaces over an `RCLike` field `𝕜`.

## Main statements

- `normalized_t_orthonormal_on_supp`: the family of normalised images `σ_i⁻¹ • T(b_E i)`,
  restricted to indices where the singular value `σ_i` is nonzero, is orthonormal in `F`.
- `inner_t_eigenbasis_sq_diag`: the Gram matrix of `T(b_E i)` is diagonal with entries `σ_i²`.
- `exists_b_f_apply_eq`: existence of an orthonormal basis `b_F` of `F` such that every column
  of `T` in the `b_E`/`b_F` bases has the indicator-weighted form
  `T(b_E i) = ∑ j, (if j = i then σ_i else 0) • b_F j`.

## Implementation notes

All theorems are stated in universally-quantified (`∀`) form so that the file needs no
file-level `variable` block.  Proofs introduce all arguments with `intro` immediately.
-/

namespace Library.LinearAlgebra.SVD.BasisConstruction

/-- The family of normalised images `σ_j⁻¹ • T(b_E j)`, restricted to indices `j` with
`j < finrank 𝕜 E` and nonzero singular value `σ_j`, is orthonormal in `F`. -/
theorem normalized_t_orthonormal_on_supp : ∀ {𝕜 : Type*} [RCLike 𝕜]
  {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
  [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
  (T : E →ₗ[𝕜] F)
  (b_E : OrthonormalBasis (Fin (Module.finrank 𝕜 E)) 𝕜 E)
  (_h_inner : ∀ i j, @inner 𝕜 _ _ (T (b_E i)) (T (b_E j)) =
    if i = j then (((T.singularValues i : ℝ)^2 : 𝕜)) else 0)
  (_h_zero : ∀ (i : Fin (Module.finrank 𝕜 E)),
    ¬((i : ℕ) < Module.finrank 𝕜 F) → T (b_E i) = 0),
  Orthonormal 𝕜
    (Set.restrict
      ({j : Fin (Module.finrank 𝕜 F) |
          ((j : ℕ) < Module.finrank 𝕜 E) ∧ (T.singularValues (j : ℕ) : ℝ) ≠ 0})
      (fun j : Fin (Module.finrank 𝕜 F) =>
        if h : (j : ℕ) < Module.finrank 𝕜 E then
          ((T.singularValues (j : ℕ) : ℝ) : 𝕜)⁻¹ • T (b_E ⟨(j : ℕ), h⟩)
        else (0 : F))) := by
  intro 𝕜 _ E F _ _ _ _ _ _ T b_E _h_inner _h_zero
  rw [orthonormal_iff_ite]
  rintro ⟨j, hj⟩ ⟨k, hk⟩
  obtain ⟨hj_lt, hj_nz⟩ := hj
  obtain ⟨hk_lt, hk_nz⟩ := hk
  simp only [Set.restrict_apply, dif_pos hj_lt, dif_pos hk_lt]
  rw [inner_smul_left, inner_smul_right]
  have hij := _h_inner ⟨j.val, hj_lt⟩ ⟨k.val, hk_lt⟩
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

/-- The Gram matrix of `T(b_E i)` is diagonal: `⟪T(b_E i), T(b_E j)⟫ = if i = j then σ_i² else 0`.
This follows from `T†∘T` being diagonal on `b_E` with eigenvalues `σ_i²`. -/
theorem inner_t_eigenbasis_sq_diag : ∀ {𝕜 : Type*} [RCLike 𝕜]
  {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
  [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
  (T : E →ₗ[𝕜] F)
  (b_E : OrthonormalBasis (Fin (Module.finrank 𝕜 E)) 𝕜 E)
  (_h_eig : ∀ i, (T.adjoint ∘ₗ T) (b_E i) =
      (((T.singularValues i : ℝ)^2 : 𝕜)) • b_E i),
  ∀ i j, @inner 𝕜 _ _ (T (b_E i)) (T (b_E j)) =
    if i = j then (((T.singularValues i : ℝ)^2 : 𝕜)) else 0 := by
  intro 𝕜 _ E F _ _ _ _ _ _ T b_E _h_eig i j
  simp only [LinearMap.comp_apply] at _h_eig
  rw [← LinearMap.adjoint_inner_left, _h_eig i, inner_smul_left]
  simp [RCLike.conj_ofReal, orthonormal_iff_ite.mp b_E.orthonormal i j]

/-- There exists an orthonormal basis `b_F` of `F` such that `T(b_E i) = σ_i • b_F ⟨i, h⟩`
for all `i` with `(i : ℕ) < finrank 𝕜 F` and `σ_i ≠ 0`. -/
theorem exists_b_f_apply_eq_nonzero : ∀ {𝕜 : Type*} [RCLike 𝕜]
  {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
  [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
  (T : E →ₗ[𝕜] F)
  (b_E : OrthonormalBasis (Fin (Module.finrank 𝕜 E)) 𝕜 E)
  (_h_inner : ∀ i j, @inner 𝕜 _ _ (T (b_E i)) (T (b_E j)) =
    if i = j then (((T.singularValues i : ℝ)^2 : 𝕜)) else 0)
  (_h_zero : ∀ (i : Fin (Module.finrank 𝕜 E)),
    ¬((i : ℕ) < Module.finrank 𝕜 F) → T (b_E i) = 0),
  ∃ (b_F : OrthonormalBasis (Fin (Module.finrank 𝕜 F)) 𝕜 F),
    ∀ (i : Fin (Module.finrank 𝕜 E)) (h : (i : ℕ) < Module.finrank 𝕜 F),
      (T.singularValues i : ℝ) ≠ 0 →
        T (b_E i) = ((T.singularValues i : ℝ) : 𝕜) • b_F ⟨(i : ℕ), h⟩  := by
  intro 𝕜 _ E F _ _ _ _ _ _ T b_E _h_inner _h_zero
  set v : Fin (Module.finrank 𝕜 F) → F := fun j =>
    if h : (j : ℕ) < Module.finrank 𝕜 E then
      ((T.singularValues (j : ℕ) : ℝ) : 𝕜)⁻¹ • T (b_E ⟨(j : ℕ), h⟩)
    else 0 with hv_def
  set s : Set (Fin (Module.finrank 𝕜 F)) :=
    {j | ((j : ℕ) < Module.finrank 𝕜 E) ∧ (T.singularValues (j : ℕ) : ℝ) ≠ 0} with hs_def
  have h_ortho : Orthonormal 𝕜 (Set.restrict s v) :=
    normalized_t_orthonormal_on_supp T b_E _h_inner _h_zero
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

/-- There exists an orthonormal basis `b_F` of `F` such that `T(b_E i)` equals
`σ_i • b_F ⟨i, h⟩` when `(i : ℕ) < finrank 𝕜 F`, and `0` otherwise.
This variant takes `h_zero` (vanishing outside the codomain rank) as a hypothesis. -/
theorem exists_b_f_apply_eq_dite_with_zero : ∀ {𝕜 : Type*} [RCLike 𝕜]
  {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
  [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
  (T : E →ₗ[𝕜] F)
  (b_E : OrthonormalBasis (Fin (Module.finrank 𝕜 E)) 𝕜 E)
  (_h_inner : ∀ i j, @inner 𝕜 _ _ (T (b_E i)) (T (b_E j)) =
    if i = j then (((T.singularValues i : ℝ)^2 : 𝕜)) else 0)
  (_h_zero : ∀ (i : Fin (Module.finrank 𝕜 E)),
    ¬((i : ℕ) < Module.finrank 𝕜 F) → T (b_E i) = 0),
  ∃ (b_F : OrthonormalBasis (Fin (Module.finrank 𝕜 F)) 𝕜 F),
    ∀ i, T (b_E i) =
      if h : (i : ℕ) < (Module.finrank 𝕜 F)
      then ((T.singularValues i : ℝ) : 𝕜) • b_F ⟨(i : ℕ), h⟩
      else 0  := by
  intro 𝕜 _ E F _ _ _ _ _ _ T b_E _h_inner _h_zero
  have h_sigma_zero := apply_basis_eq_zero_of_singularValues_zero T b_E _h_inner _h_zero
  have h_main := exists_b_f_apply_eq_nonzero T b_E _h_inner _h_zero
  obtain ⟨b_F, h_low⟩ := h_main
  refine ⟨b_F, fun i => ?_⟩
  by_cases h : (i : ℕ) < Module.finrank 𝕜 F
  · rw [dif_pos h]
    by_cases hσ : (T.singularValues i : ℝ) = 0
    · rw [h_sigma_zero i hσ, hσ]; simp
    · exact h_low i h hσ
  · rw [dif_neg h]; exact _h_zero i h

/-- The indicator-weighted sum `∑ j, (if j = i then σ_i else 0) • b_F j` equals
`σ_i • b_F ⟨i, h⟩` when `(i : ℕ) < finrank 𝕜 F`, and `0` otherwise.
This is a purely algebraic identity used to rewrite the column-sum form of `T`. -/
theorem sum_ite_smul_eq_dite : ∀ {𝕜 : Type*} [RCLike 𝕜]
  {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
  [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
  (T : E →ₗ[𝕜] F)
  (b_E : OrthonormalBasis (Fin (Module.finrank 𝕜 E)) 𝕜 E)
  (_h_inner : ∀ i j, @inner 𝕜 _ _ (T (b_E i)) (T (b_E j)) =
    if i = j then (((T.singularValues i : ℝ)^2 : 𝕜)) else 0)
  (b_F : OrthonormalBasis (Fin (Module.finrank 𝕜 F)) 𝕜 F)
  (i : Fin (Module.finrank 𝕜 E)),
    (∑ j : Fin (Module.finrank 𝕜 F),
      (if (j : ℕ) = (i : ℕ) then ((T.singularValues i : ℝ) : 𝕜) else 0) • b_F j) =
    if h : (i : ℕ) < (Module.finrank 𝕜 F)
    then ((T.singularValues i : ℝ) : 𝕜) • b_F ⟨(i : ℕ), h⟩
    else 0 := by
  intro 𝕜 _ E F _ _ _ _ _ _ T b_E _h_inner b_F i
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

/-- There exists an orthonormal basis `b_F` of `F` such that `T(b_E i)` equals
`σ_i • b_F ⟨i, h⟩` when `(i : ℕ) < finrank 𝕜 F`, and `0` otherwise. -/
theorem b_f_apply_eq_dite : ∀ {𝕜 : Type*} [RCLike 𝕜]
  {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
  [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
  (T : E →ₗ[𝕜] F)
  (b_E : OrthonormalBasis (Fin (Module.finrank 𝕜 E)) 𝕜 E)
  (_h_inner : ∀ i j, @inner 𝕜 _ _ (T (b_E i)) (T (b_E j)) =
    if i = j then (((T.singularValues i : ℝ)^2 : 𝕜)) else 0),
  ∃ (b_F : OrthonormalBasis (Fin (Module.finrank 𝕜 F)) 𝕜 F),
    ∀ i, T (b_E i) =
      if h : (i : ℕ) < (Module.finrank 𝕜 F)
      then ((T.singularValues i : ℝ) : 𝕜) • b_F ⟨(i : ℕ), h⟩
      else 0  := by
  intro 𝕜 _ E F _ _ _ _ _ _ T b_E _h_inner
  have h_zero := apply_basis_eq_zero_of_not_lt_finrank T b_E _h_inner
  exact exists_b_f_apply_eq_dite_with_zero T b_E _h_inner h_zero

/-- There exists an orthonormal basis `b_F` of `F` such that for every `i`,
`T(b_E i) = ∑ j, (if j = i then σ_i else 0) • b_F j`.
This is the column-sum form of the SVD column property, obtained by combining
`b_f_apply_eq_dite` with the algebraic identity `sum_ite_smul_eq_dite`. -/
theorem exists_b_f_apply_eq : ∀ {𝕜 : Type*} [RCLike 𝕜]
  {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
  [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
  (T : E →ₗ[𝕜] F)
  (b_E : OrthonormalBasis (Fin (Module.finrank 𝕜 E)) 𝕜 E)
  (_h_inner : ∀ i j, @inner 𝕜 _ _ (T (b_E i)) (T (b_E j)) =
    if i = j then (((T.singularValues i : ℝ)^2 : 𝕜)) else 0),
  ∃ (b_F : OrthonormalBasis (Fin (Module.finrank 𝕜 F)) 𝕜 F),
    ∀ i, T (b_E i) = ∑ j : Fin (Module.finrank 𝕜 F),
      (if (j : ℕ) = (i : ℕ) then ((T.singularValues i : ℝ) : 𝕜) else 0) • b_F j := by
  intro 𝕜 _ E F _ _ _ _ _ _ T b_E _h_inner
  obtain ⟨b_F, h_col⟩ := b_f_apply_eq_dite T b_E _h_inner
  refine ⟨b_F, fun i => ?_⟩
  rw [sum_ite_smul_eq_dite T b_E _h_inner b_F i]
  exact h_col i

end Library.LinearAlgebra.SVD.BasisConstruction
