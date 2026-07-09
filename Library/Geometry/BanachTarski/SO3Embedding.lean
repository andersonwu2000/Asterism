import Mathlib.Data.Real.StarOrdered
import Library.Geometry.BanachTarski.Defs
import Library.Geometry.BanachTarski.FixedSetLemmas
import Library.Geometry.BanachTarski.OrthogonalMatrices
import Library.Geometry.BanachTarski.RotationWordNe1

/-!
# SO(3) Embedding of the Free Group

This file constructs an explicit embedding of the free group on two generators,
`FreeGroup (Fin 2)`, into the group of linear isometry equivalences of
$E = \text{EuclideanSpace}\ \mathbb{R}\ (\text{Fin}\ 3)$, realized as a subgroup of $SO(3)$.

## Main statements

- `matrix_rep_monoid_hom`: the map sending a linear isometry equivalence to its matrix in
  the standard Euclidean basis is an injective monoid homomorphism compatible with determinants.
- `free_so3_embedding`: there exists an injective group homomorphism
  `ψ : FreeGroup (Fin 2) →* (E ≃ₗᵢ[ℝ] E)` whose image lies in $SO(3)$.
- `exists_free_isometry_embedding`: there exists an injective group homomorphism
  `φ : FreeGroup (Fin 2) →* (E ≃ᵢ E)` fixing the origin, with finite fixed-point sets on
  the unit sphere for every non-identity word.

## Implementation notes

The two generators are explicit rotation matrices of the form $(1/3) \cdot M$ for specific
integer matrices $M$ with $\sqrt{2}$ entries. Orthogonality and determinant-one are verified
by `nlinarith` after `fin_cases`.
-/

open Library.Geometry.BanachTarski.Defs
open Library.Geometry.BanachTarski.FixedSetLemmas
open Library.Geometry.BanachTarski.OrthogonalMatrices
open Library.Geometry.BanachTarski.RotationWordNe1
open Matrix

namespace Library.Geometry.BanachTarski.SO3Embedding

/-- The matrix $A^{-1} A = 1$ for the first generator, where
$A = (1/3) \cdot \text{!![1, -2√2, 0; 2√2, 1, 0; 0, 0, 3]}$. -/
theorem a_inv_left_inverse (A AInv : Matrix (Fin 3) (Fin 3) ℝ)
    (hA : A = (1 / 3 : ℝ) • !![1, -2 * Real.sqrt 2, 0; 2 * Real.sqrt 2, 1, 0; 0, 0, 3])
    (hAInv : AInv = (1 / 3 : ℝ) • !![1, 2 * Real.sqrt 2, 0; -2 * Real.sqrt 2, 1, 0; 0, 0, 3]) :
    AInv * A = 1 := by
  subst hA hAInv
  have hsq : Real.sqrt 2 * Real.sqrt 2 = 2 := Real.mul_self_sqrt (by norm_num)
  ext i j
  fin_cases i <;> fin_cases j <;>
    simp [Matrix.mul_apply, Fin.sum_univ_three] <;>
    ring_nf <;>
    nlinarith

/-- The matrix $B^{-1} B = 1$ for the second generator, where
$B = (1/3) \cdot \text{!![3, 0, 0; 0, 1, -2√2; 0, 2√2, 1]}$. -/
theorem b_inv_left_inverse (B BInv : Matrix (Fin 3) (Fin 3) ℝ)
    (hB : B = (1 / 3 : ℝ) • !![3, 0, 0; 0, 1, -2 * Real.sqrt 2; 0, 2 * Real.sqrt 2, 1])
    (hBInv : BInv = (1 / 3 : ℝ) • !![3, 0, 0; 0, 1, 2 * Real.sqrt 2; 0, -2 * Real.sqrt 2, 1]) :
    BInv * B = 1 := by
  subst hB hBInv
  have h2 : Real.sqrt 2 ^ 2 = 2 := Real.sq_sqrt (by norm_num)
  ext i j
  fin_cases i <;> fin_cases j <;>
    simp [Matrix.mul_apply, Fin.sum_univ_three, Matrix.cons_val',
          Matrix.cons_val_zero, Matrix.cons_val_one] <;>
    ring_nf <;> nlinarith [h2]

/-- There exists an injective monoid homomorphism
`mat : (E ≃ₗᵢ[ℝ] E) →* Matrix (Fin 3) (Fin 3) ℝ` that represents each linear isometry
equivalence as a matrix in the standard `EuclideanSpace` basis, is compatible with
determinants via `LinearMap.det_toMatrix`, and recovers the matrix from the action on
`EuclideanSpace`. -/
theorem matrix_rep_monoid_hom :
    ∃ mat : (E ≃ₗᵢ[ℝ] E) →* Matrix (Fin 3) (Fin 3) ℝ,
      Function.Injective mat ∧
      (∀ T : E ≃ₗᵢ[ℝ] E, (mat T).det = LinearMap.det (T.toLinearEquiv.toLinearMap)) ∧
      (∀ (T : E ≃ₗᵢ[ℝ] E) (M : Matrix (Fin 3) (Fin 3) ℝ),
          (∀ x : E, T x = Matrix.toEuclideanLin M x) → mat T = M)  := by
  set b := (EuclideanSpace.basisFun (Fin 3) ℝ).toBasis with hb
  refine ⟨{
    toFun := fun T => LinearMap.toMatrix b b T.toLinearEquiv.toLinearMap
    map_one' := by
      have : ((1 : E ≃ₗᵢ[ℝ] E).toLinearEquiv.toLinearMap) = 1 := by ext x; rfl
      rw [this, LinearMap.toMatrix_one]
    map_mul' := by
      intro T₁ T₂
      have : ((T₁ * T₂).toLinearEquiv.toLinearMap)
          = (T₁.toLinearEquiv.toLinearMap) * (T₂.toLinearEquiv.toLinearMap) := by ext x; rfl
      rw [this, LinearMap.toMatrix_mul]
  }, ?_, ?_, ?_⟩
  · intro T₁ T₂ h
    simp only [MonoidHom.coe_mk, OneHom.coe_mk] at h
    have h2 : (T₁.toLinearEquiv.toLinearMap) = (T₂.toLinearEquiv.toLinearMap) :=
      (LinearMap.toMatrix b b).injective h
    have h3 : T₁.toLinearEquiv = T₂.toLinearEquiv := LinearEquiv.toLinearMap_injective h2
    exact LinearIsometryEquiv.toLinearEquiv_injective h3
  · intro T
    simp only [MonoidHom.coe_mk, OneHom.coe_mk]
    exact LinearMap.det_toMatrix b _
  · intro T M hTM
    simp only [MonoidHom.coe_mk, OneHom.coe_mk]
    have : T.toLinearEquiv.toLinearMap = Matrix.toEuclideanLin M :=
      LinearMap.ext fun x => hTM x
    rw [this]
    exact (LinearEquiv.eq_symm_apply (LinearMap.toMatrix b b)).mp rfl

/-- An orthogonal matrix $M$ (satisfying $M^T M = 1$) induces a `LinearIsometryEquiv` of $E$
acting pointwise by `Matrix.toEuclideanLin M`. -/
theorem orthogonal_to_linear_isometry_equiv
    (M : Matrix (Fin 3) (Fin 3) ℝ) (hM : Matrix.transpose M * M = 1) :
    ∃ e : E ≃ₗᵢ[ℝ] E, ∀ x : E, e x = Matrix.toEuclideanLin M x := by
  have h_inner : ∀ x y : E,
      inner ℝ (Matrix.toEuclideanLin M x) (Matrix.toEuclideanLin M y) = inner ℝ x y :=
    orthogonal_matrix_preserves_inner M hM
  have hnorm : ∀ x : E, ‖Matrix.toEuclideanLin M x‖ = ‖x‖ := by
    intro x
    have := h_inner x x
    simp only [real_inner_self_eq_norm_sq] at this
    nlinarith [norm_nonneg (Matrix.toEuclideanLin M x), norm_nonneg x]
  let f : E →ₗᵢ[ℝ] E := ⟨Matrix.toEuclideanLin M, hnorm⟩
  have hinj : Function.Injective f.toLinearMap := f.injective
  have hsurj : Function.Surjective f.toLinearMap := by
    apply (f.toLinearMap.injective_iff_surjective_of_finrank_eq_finrank _).mp hinj
    rfl
  exact ⟨LinearIsometryEquiv.ofSurjective f hsurj, fun x => rfl⟩

/-- Realizes two concrete rotation generators as linear isometry equivalences of $E$, together
with an injective matrix representation `mat` that records each generator's explicit
$3 \times 3$ matrix and its inverse. -/
theorem so3_realization_hom :
    ∃ (g : Fin 2 → (E ≃ₗᵢ[ℝ] E)) (mat : (E ≃ₗᵢ[ℝ] E) →* Matrix (Fin 3) (Fin 3) ℝ),
      Function.Injective mat ∧
      (∀ T : E ≃ₗᵢ[ℝ] E, (mat T).det = LinearMap.det (T.toLinearEquiv.toLinearMap)) ∧
      mat (g 0) = (1/3:ℝ) • !![1, -2*Real.sqrt 2, 0; 2*Real.sqrt 2, 1, 0; 0, 0, 3] ∧
      (mat (g 0))⁻¹ = (1/3:ℝ) • !![1, 2*Real.sqrt 2, 0; -2*Real.sqrt 2, 1, 0; 0, 0, 3] ∧
      mat (g 1) = (1/3:ℝ) • !![3, 0, 0; 0, 1, -2*Real.sqrt 2; 0, 2*Real.sqrt 2, 1] ∧
      (mat (g 1))⁻¹ = (1/3:ℝ) • !![3, 0, 0; 0, 1, 2*Real.sqrt 2; 0, -2*Real.sqrt 2, 1]  := by
  have hoA : Matrix.transpose ((1/3:ℝ) • !![1, -2*Real.sqrt 2, 0; 2*Real.sqrt 2, 1, 0; 0, 0, 3])
      * ((1/3:ℝ) • !![1, -2*Real.sqrt 2, 0; 2*Real.sqrt 2, 1, 0; 0, 0, 3]) = 1 := by
    have h2 : Real.sqrt 2 ^ 2 = 2 := Real.sq_sqrt (by norm_num)
    ext i j
    fin_cases i <;> fin_cases j <;>
      simp [Matrix.transpose, Matrix.mul_apply, Fin.sum_univ_three, Matrix.smul_apply] <;>
      nlinarith [h2]
  have hoB : Matrix.transpose ((1/3:ℝ) • !![3, 0, 0; 0, 1, -2*Real.sqrt 2; 0, 2*Real.sqrt 2, 1])
      * ((1/3:ℝ) • !![3, 0, 0; 0, 1, -2*Real.sqrt 2; 0, 2*Real.sqrt 2, 1]) = 1 := by
    have hsq : Real.sqrt 2 * Real.sqrt 2 = 2 := Real.mul_self_sqrt (by norm_num)
    ext i j
    fin_cases i <;> fin_cases j <;>
      simp [Matrix.transpose, Matrix.mul_apply, Fin.sum_univ_three, Matrix.smul_apply,
            Matrix.cons_val_zero, Matrix.cons_val_one] <;>
      ring_nf <;>
      nlinarith [hsq, sq_nonneg (Real.sqrt 2)]
  obtain ⟨mat, hinj, hdet, hcomp⟩ := matrix_rep_monoid_hom
  obtain ⟨eA, heA⟩ := orthogonal_to_linear_isometry_equiv _ hoA
  obtain ⟨eB, heB⟩ := orthogonal_to_linear_isometry_equiv _ hoB
  refine ⟨![eA, eB], mat, hinj, hdet, ?_, ?_, ?_, ?_⟩
  · change mat eA = _
    exact hcomp eA _ heA
  · change (mat eA)⁻¹ = _
    rw [hcomp eA _ heA]
    exact Matrix.inv_eq_left_inv (a_inv_left_inverse _ _ rfl rfl)
  · change mat eB = _
    exact hcomp eB _ heB
  · change (mat eB)⁻¹ = _
    rw [hcomp eB _ heB]
    exact Matrix.inv_eq_left_inv (b_inv_left_inverse _ _ rfl rfl)

/-- The determinant of the first generator matrix
$(1/3) \cdot \text{!![1, -2√2, 0; 2√2, 1, 0; 0, 0, 3]}$ equals $1$. -/
theorem gen_a_det_one :
    ((1/3:ℝ) • !![1, -2*Real.sqrt 2, 0; 2*Real.sqrt 2, 1, 0; 0, 0, 3] :
      Matrix (Fin 3) (Fin 3) ℝ).det = 1 := by
  have hsq : Real.sqrt 2 * Real.sqrt 2 = 2 := Real.mul_self_sqrt (by norm_num)
  have hdet : (!![1, -2*Real.sqrt 2, 0; 2*Real.sqrt 2, 1, 0; 0, 0, 3] :
      Matrix (Fin 3) (Fin 3) ℝ).det = 27 := by
    rw [Matrix.det_fin_three]
    have hv1 : (![1, -(2 * Real.sqrt 2), 0] : Fin 3 → ℝ) 2 = 0 := rfl
    have hv2 : (![2 * Real.sqrt 2, 1, 0] : Fin 3 → ℝ) 2 = 0 := rfl
    have hv3 : (![0, 0, 3] : Fin 3 → ℝ) 2 = 3 := rfl
    norm_num [hv1, hv2, hv3, Matrix.cons_val_succ, Matrix.cons_val_zero]
    have hc : Matrix.vecCons (0 : ℝ)
        (fun i : Fin 2 ↦ Matrix.vecCons (0 : ℝ) (fun _ : Fin 1 ↦ (3 : ℝ)) i)
        (2 : Fin 3) = 3 := by simp
    nlinarith [hsq, hc]
  rw [Matrix.det_smul, hdet]; norm_num

/-- The determinant of the second generator matrix
$(1/3) \cdot \text{!![3, 0, 0; 0, 1, -2√2; 0, 2√2, 1]}$ equals $1$. -/
theorem gen_b_det_one :
    ((1/3:ℝ) • !![3, 0, 0; 0, 1, -2*Real.sqrt 2; 0, 2*Real.sqrt 2, 1] :
      Matrix (Fin 3) (Fin 3) ℝ).det = 1 := by
  simp [Matrix.det_fin_three]
  ring_nf
  norm_num [Real.sq_sqrt]

/-- For any word `w` in `FreeGroup (Fin 2)`, the `LinearMap.det` of `FreeGroup.lift g w`
equals $1$, given that the matrix representations of both generators have determinant $1$.
The proof uses `Matrix.detMonoidHom` and free-group induction. -/
theorem lift_det_one
    (g : Fin 2 → (E ≃ₗᵢ[ℝ] E))
    (mat : (E ≃ₗᵢ[ℝ] E) →* Matrix (Fin 3) (Fin 3) ℝ)
    (hmatdet : ∀ T : E ≃ₗᵢ[ℝ] E, (mat T).det = LinearMap.det (T.toLinearEquiv.toLinearMap))
    (hdetA : (mat (g 0)).det = 1) (hdetB : (mat (g 1)).det = 1)
    (w : FreeGroup (Fin 2)) :
    LinearMap.det ((FreeGroup.lift g w).toLinearEquiv.toLinearMap) = 1  := by
  have key : ∀ v : FreeGroup (Fin 2),
      (Matrix.detMonoidHom.comp (mat.comp (FreeGroup.lift g))) v = 1 := by
    intro v
    induction v using FreeGroup.induction_on with
    | C1 => simp
    | of x => fin_cases x <;> simp [hdetA, hdetB]
    | inv_of x ih =>
        have h2 := (Matrix.detMonoidHom.comp (mat.comp (FreeGroup.lift g))).map_mul
          (FreeGroup.of x)⁻¹ (FreeGroup.of x)
        simp only [inv_mul_cancel, map_one, ih, mul_one] at h2
        exact h2.symm
    | mul x y ihx ihy => rw [map_mul, ihx, ihy, mul_one]
  rw [← hmatdet]
  exact key w

/-- Given that the matrix word-product is non-trivial for every non-identity free-group element,
shows that the corresponding word-product of the generators `g 0`, `g 1` is also non-trivial. -/
theorem gen_word_prod_ne_one
    (g : Fin 2 → (E ≃ₗᵢ[ℝ] E))
    (mat : (E ≃ₗᵢ[ℝ] E) →* Matrix (Fin 3) (Fin 3) ℝ)
    (A AInv B BInv : Matrix (Fin 3) (Fin 3) ℝ)
    (_hinj : Function.Injective mat)
    (hg0 : mat (g 0) = A) (hg0inv : (mat (g 0))⁻¹ = AInv)
    (hg1 : mat (g 1) = B) (hg1inv : (mat (g 1))⁻¹ = BInv)
    (hword : ∀ w : FreeGroup (Fin 2), w ≠ 1 →
      ((FreeGroup.toWord w).map (fun x : Fin 2 × Bool =>
         if x.1 = 0 then (if x.2 then A else AInv)
                    else (if x.2 then B else BInv))).prod ≠ 1) :
    ∀ v : FreeGroup (Fin 2), FreeGroup.toWord v ≠ [] →
      ((FreeGroup.toWord v).map (fun x : Fin 2 × Bool =>
        if x.2 then g x.1 else (g x.1)⁻¹)).prod ≠ 1 := by
  intro v hv
  have hv1 : v ≠ 1 := fun h => hv (FreeGroup.toWord_eq_nil_iff.mpr h)
  intro hcontra
  apply hword v hv1
  have mat_inv_g0 : mat ((g 0)⁻¹) = AInv := by
    have h : mat (g 0) * mat ((g 0)⁻¹) = 1 := by
      rw [← map_mul, mul_inv_cancel, map_one]
    rw [← hg0inv]; exact (Matrix.inv_eq_right_inv h).symm
  have mat_inv_g1 : mat ((g 1)⁻¹) = BInv := by
    have h : mat (g 1) * mat ((g 1)⁻¹) = 1 := by
      rw [← map_mul, mul_inv_cancel, map_one]
    rw [← hg1inv]; exact (Matrix.inv_eq_right_inv h).symm
  have key : ∀ x : Fin 2 × Bool,
      mat (if x.2 then g x.1 else (g x.1)⁻¹) =
      if x.1 = 0 then (if x.2 then A else AInv) else (if x.2 then B else BInv) := by
    intro ⟨i, b⟩
    fin_cases i <;> fin_cases b <;>
      simp only [Fin.zero_eta, Fin.reduceEq, ↓reduceIte, Fin.mk_one, Bool.false_eq_true]
    · exact hg0
    · exact mat_inv_g0
    · exact hg1
    · exact mat_inv_g1
  have hbridge : mat ((FreeGroup.toWord v).map
      (fun x : Fin 2 × Bool => if x.2 then g x.1 else (g x.1)⁻¹)).prod =
      ((FreeGroup.toWord v).map (fun x : Fin 2 × Bool =>
      if x.1 = 0 then (if x.2 then A else AInv) else (if x.2 then B else BInv))).prod := by
    rw [map_list_prod, List.map_map]
    congr 1
    apply List.map_congr_left
    intro x _
    exact key x
  rw [← hbridge, hcontra, map_one]

/-- If every non-identity word `w` maps to a non-trivial matrix product
(as expressed by `hword`), then `FreeGroup.lift g w ≠ 1` for every non-identity `w`. -/
theorem lift_ne_one
    (g : Fin 2 → (E ≃ₗᵢ[ℝ] E))
    (mat : (E ≃ₗᵢ[ℝ] E) →* Matrix (Fin 3) (Fin 3) ℝ)
    (A AInv B BInv : Matrix (Fin 3) (Fin 3) ℝ)
    (hinj : Function.Injective mat)
    (hg0 : mat (g 0) = A) (hg0inv : (mat (g 0))⁻¹ = AInv)
    (hg1 : mat (g 1) = B) (hg1inv : (mat (g 1))⁻¹ = BInv)
    (hword : ∀ w : FreeGroup (Fin 2), w ≠ 1 →
      ((FreeGroup.toWord w).map (fun x : Fin 2 × Bool =>
         if x.1 = 0 then (if x.2 then A else AInv)
                    else (if x.2 then B else BInv))).prod ≠ 1)
    (w : FreeGroup (Fin 2)) (hw : w ≠ 1) :
    FreeGroup.lift g w ≠ 1  := by
  have hgprod := gen_word_prod_ne_one g mat A AInv B BInv hinj hg0 hg0inv hg1 hg1inv hword
  have hinjlift : Function.Injective (FreeGroup.lift g) :=
    freegroup_lift_injective_of_word_prod_ne_one g hgprod
  intro hc
  exact hw (hinjlift (by rw [hc, map_one]))

/-- **Free SO(3) embedding**: there exists an injective monoid homomorphism
`ψ : FreeGroup (Fin 2) →* (E ≃ₗᵢ[ℝ] E)` such that for every non-identity word `w`,
the determinant of `ψ w` is $1$ and `ψ w` is not the identity isometry.

The homomorphism is `FreeGroup.lift g` for generators `g 0`, `g 1` from
`so3_realization_hom`. Non-triviality of words is transported from the matrix level via
injectivity of `mat`. -/
theorem free_so3_embedding :
    ∃ ψ : FreeGroup (Fin 2) →* (E ≃ₗᵢ[ℝ] E),
      Function.Injective ψ ∧
      (∀ w : FreeGroup (Fin 2), w ≠ 1 →
        LinearMap.det ((ψ w).toLinearEquiv.toLinearMap) = 1 ∧
        ψ w ≠ LinearIsometryEquiv.refl ℝ E)  := by
  obtain ⟨g, mat, hmatinj, hmatdet, hg0, hg0inv, hg1, hg1inv⟩ := so3_realization_hom
  have hdetA : (mat (g 0)).det = 1 := by rw [hg0]; exact gen_a_det_one
  have hdetB : (mat (g 1)).det = 1 := by rw [hg1]; exact gen_b_det_one
  have hword : ∀ w : FreeGroup (Fin 2), w ≠ 1 →
      ((FreeGroup.toWord w).map (fun x : Fin 2 × Bool =>
         if x.1 = 0 then (if x.2 then mat (g 0) else (mat (g 0))⁻¹)
                    else (if x.2 then mat (g 1) else (mat (g 1))⁻¹))).prod ≠ 1 := by
    intro w hw
    simp only [hg0inv, hg1inv]
    simp only [hg0, hg1]
    exact rotation_word_ne_one_of_reduced _ _ _ _ rfl rfl rfl rfl w hw
  refine ⟨FreeGroup.lift g, ?_, ?_⟩
  · rw [injective_iff_map_eq_one]
    intro w hw
    by_contra hne
    exact lift_ne_one g mat (mat (g 0)) (mat (g 0))⁻¹ (mat (g 1)) (mat (g 1))⁻¹
      hmatinj rfl rfl rfl rfl hword w hne hw
  · intro w hw
    refine ⟨lift_det_one g mat hmatdet hdetA hdetB w, ?_⟩
    have h := lift_ne_one g mat (mat (g 0)) (mat (g 0))⁻¹ (mat (g 1)) (mat (g 1))⁻¹
      hmatinj rfl rfl rfl rfl hword w hw
    intro hc; exact h (by rw [hc]; rfl)

/-- There exists an injective group homomorphism `φ : FreeGroup (Fin 2) →* (E ≃ᵢ E)` such that
every `φ w` fixes the origin and, for every non-identity word `w`, the fixed-point set of `φ w`
on the unit sphere is finite.

This is obtained by composing the SO(3) embedding `ψ` from `free_so3_embedding` with the
coercion `(E ≃ₗᵢ[ℝ] E) →* (E ≃ᵢ E)`. Finiteness of fixed points follows from
`rotation_fixed_set_on_sphere_finite`. -/
theorem exists_free_isometry_embedding :
    ∃ φ : FreeGroup (Fin 2) →* (E ≃ᵢ E),
      Function.Injective φ ∧
      (∀ w : FreeGroup (Fin 2), φ w 0 = 0) ∧
      (∀ w : FreeGroup (Fin 2), w ≠ 1 →
        {x ∈ Metric.sphere (0 : E) 1 | φ w x = x}.Finite)  := by
  obtain ⟨ψ, hinj, hprop⟩ := free_so3_embedding
  let c : (E ≃ₗᵢ[ℝ] E) →* (E ≃ᵢ E) :=
    { toFun := fun g => g.toIsometryEquiv
      map_one' := rfl
      map_mul' := fun a b => rfl }
  have hcinj : Function.Injective c := fun x y hxy =>
    LinearIsometryEquiv.toIsometryEquiv_injective hxy
  refine ⟨c.comp ψ, ?_, ?_, ?_⟩
  · exact hcinj.comp hinj
  · intro w
    change (ψ w).toIsometryEquiv 0 = 0
    simp
  · intro w hw
    obtain ⟨hdet, hne⟩ := hprop w hw
    have hfin := rotation_fixed_set_on_sphere_finite (ψ w) hdet hne
    convert hfin using 2

end Library.Geometry.BanachTarski.SO3Embedding
