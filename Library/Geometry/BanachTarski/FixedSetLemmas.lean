import Mathlib.AlgebraicTopology.SimplexCategory.Basic
import Mathlib.LinearAlgebra.FreeModule.PID
import Mathlib.RingTheory.Flat.FaithfullyFlat.Basic
import Mathlib.RingTheory.Flat.TorsionFree
import Mathlib.RingTheory.SimpleRing.Principal
import Library.Geometry.BanachTarski.Defs

/-!
# Fixed-set lemmas for rotations in Euclidean space

This file collects auxiliary lemmas about fixed sets and eigenspaces that arise in the
proof of the Banach–Tarski paradox. The central result is
`rotation_fixed_set_on_sphere_finite`: every non-trivial orientation-preserving isometry
of `E` (a 3-dimensional real inner product space) has a finite fixed-point set on the
unit sphere.

## Main statements

- `sphere_inter_finrank_le_one_finite`: the intersection of the unit sphere with a
  submodule of `finrank ≤ 1` is finite.
- `linearMap_eq_prodMap_restrict_of_isCompl`: a linear map equals the conjugate of the
  product of its restrictions to two complementary invariant submodules.
- `det_eq_prod_det_restrict_invariant`: the determinant of a linear map splits as the
  product of determinants on complementary invariant submodules.
- `invariant_submodule_image_surj`: a linear isometry restricted to a finite-dimensional
  invariant submodule is surjective onto that submodule.
- `isometry_fixed_complement_invariant`: the orthogonal complement of an invariant
  submodule is itself invariant under a linear isometry.
- `endo_finrank_one_eq_smul_id`: every endomorphism of a 1-dimensional real inner
  product space is a scalar multiple of the identity.
- `endo_finrank_le_one_eq_det_smul`: every endomorphism of a `finrank ≤ 1` real inner
  product space acts as multiplication by its determinant.
- `rotation_eigenspace_one_finrank_le_one`: the $1$-eigenspace of a non-trivial
  determinant-one isometry has `finrank ≤ 1`.
- `rotation_fixed_set_on_sphere_finite`: the fixed-point set on the unit sphere of a
  non-trivial rotation is finite.
-/

open Library.Geometry.BanachTarski.Defs

namespace Library.Geometry.BanachTarski.FixedSetLemmas

/-- If `W` is a submodule of `E` with `finrank ℝ W ≤ 1`, then the intersection of `W`
with the unit sphere is finite. Every element of `W` is a scalar multiple of a fixed
generator `v`; a unit-norm element `c • v` forces `|c| = ‖v‖⁻¹`, so the intersection
is contained in the two-element set `{‖v‖⁻¹ • v, -‖v‖⁻¹ • v}`. -/
theorem sphere_inter_finrank_le_one_finite
    (W : Submodule ℝ E) (hW : Module.finrank ℝ W ≤ 1) :
    {x ∈ Metric.sphere (0 : E) 1 | x ∈ W}.Finite := by
  have h1 : ∃ v : E, ∀ x ∈ W, ∃ c : ℝ, x = c • v := by
    obtain ⟨v, hv⟩ := (finrank_le_one_iff (K := ℝ) (V := ↥W)).mp hW
    refine ⟨(v : E), fun x hx => ?_⟩
    obtain ⟨c, hc⟩ := hv ⟨x, hx⟩
    exact ⟨c, by simpa using congrArg (Subtype.val) hc.symm⟩
  obtain ⟨v, hv⟩ := h1
  apply Set.Finite.subset (s := {(‖v‖⁻¹ : ℝ) • v, (-(‖v‖⁻¹) : ℝ) • v})
  · exact (Set.finite_singleton _).insert _
  · intro x hx
    simp only [Set.mem_setOf_eq, Metric.mem_sphere, dist_eq_norm, sub_zero] at hx
    obtain ⟨hnorm, hxW⟩ := hx
    obtain ⟨c, rfl⟩ := hv x hxW
    rw [norm_smul, Real.norm_eq_abs] at hnorm
    have hc : |c| = ‖v‖⁻¹ := by
      rw [mul_comm] at hnorm; exact eq_inv_of_mul_eq_one_right hnorm
    rw [Set.mem_insert_iff, Set.mem_singleton_iff]
    rcases (abs_eq (by positivity)).mp hc with h | h
    · exact Or.inl (by rw [h])
    · exact Or.inr (by rw [h])

/-- A linear map `T` on `F` that leaves two complementary submodules `W` and `W'`
invariant is conjugate to the product of its restrictions. Concretely,
`T = e ∘ (T|_W × T|_{W'}) ∘ e⁻¹` where `e : W × W' ≃ F` is the canonical
isomorphism from the complementary decomposition. -/
theorem linearMap_eq_prodMap_restrict_of_isCompl
    {𝕜 : Type*} [Field 𝕜] {F : Type*} [AddCommGroup F] [Module 𝕜 F]
    (T : F →ₗ[𝕜] F) (W W' : Submodule 𝕜 F)
    (hW : ∀ x ∈ W, T x ∈ W) (hW' : ∀ x ∈ W', T x ∈ W')
    (hcompl : IsCompl W W') :
    T = (Submodule.prodEquivOfIsCompl W W' hcompl).toLinearMap.comp
        ((LinearMap.prodMap (T.restrict hW) (T.restrict hW')).comp
          (Submodule.prodEquivOfIsCompl W W' hcompl).symm.toLinearMap) := by
  set e := W.prodEquivOfIsCompl W' hcompl
  set f := (T.restrict hW).prodMap (T.restrict hW')
  have hcomp : T.comp e.toLinearMap = e.toLinearMap.comp f := by
    apply LinearMap.ext
    rintro ⟨⟨w, hw⟩, ⟨w', hw'⟩⟩
    simp only [LinearMap.comp_apply, LinearEquiv.coe_toLinearMap]
    simp only [f, LinearMap.prodMap_apply, LinearMap.restrict_apply]
    change T (w + w') = T w + T w'
    exact map_add T w w'
  ext x
  have hx : T x = T (e (e.symm x)) := by rw [e.apply_symm_apply]
  rw [hx]
  have h2 : T (e (e.symm x)) = e (f (e.symm x)) := by
    have := congr($(hcomp) (e.symm x))
    simp only [LinearMap.comp_apply, LinearEquiv.coe_toLinearMap] at this
    exact this
  simp only [LinearMap.comp_apply, LinearEquiv.coe_toLinearMap, h2]

/-- The determinant of a linear map `T : F →ₗ[𝕜] F` equals the product of the
determinants of its restrictions to two `T`-invariant submodules `W` and `W'` that
form a complementary decomposition `W ⊓ W' = ⊥`, `W ⊔ W' = ⊤`. -/
theorem det_eq_prod_det_restrict_invariant
    {𝕜 : Type*} [Field 𝕜] {F : Type*} [AddCommGroup F] [Module 𝕜 F]
    [FiniteDimensional 𝕜 F]
    (T : F →ₗ[𝕜] F) (W W' : Submodule 𝕜 F)
    (hW : ∀ x ∈ W, T x ∈ W) (hW' : ∀ x ∈ W', T x ∈ W')
    (hbot : W ⊓ W' = ⊥) (htop : W ⊔ W' = ⊤) :
    LinearMap.det T
      = LinearMap.det (T.restrict hW) * LinearMap.det (T.restrict hW') := by
  have hcompl : IsCompl W W' := ⟨disjoint_iff.mpr hbot, codisjoint_iff.mpr htop⟩
  have h_conj := linearMap_eq_prodMap_restrict_of_isCompl T W W' hW hW' hcompl
  conv_lhs => rw [h_conj]
  rw [LinearMap.det_conj, LinearMap.det_prodMap]

/-- If `T` is a linear isometry of a finite-dimensional real inner product space `F` and
`W` is a `T`-invariant submodule, then `T` maps `W` surjectively onto itself. -/
theorem invariant_submodule_image_surj
    {F : Type*} [NormedAddCommGroup F] [InnerProductSpace ℝ F]
    [FiniteDimensional ℝ F]
    (T : F ≃ₗᵢ[ℝ] F) (W : Submodule ℝ F)
    (hW : ∀ x ∈ W, T x ∈ W) :
    ∀ w ∈ W, ∃ y ∈ W, T y = w := by
  have hmap : W.map T.toLinearEquiv.toLinearMap ≤ W := by
    rintro x ⟨y, hy, rfl⟩
    exact hW y hy
  have hfin : Module.finrank ℝ (W.map T.toLinearEquiv.toLinearMap)
      = Module.finrank ℝ W := T.toLinearEquiv.finrank_map_eq W
  have heq : W.map T.toLinearEquiv.toLinearMap = W :=
    Submodule.eq_of_le_of_finrank_eq hmap hfin
  intro w hw
  rw [← heq] at hw
  obtain ⟨y, hy, hTy⟩ := hw
  exact ⟨y, hy, hTy⟩

/-- If a linear isometry `T` of a finite-dimensional real inner product space leaves a
submodule `W` invariant, then it also leaves the orthogonal complement `Wᗮ` invariant. -/
theorem isometry_fixed_complement_invariant
    {F : Type*} [NormedAddCommGroup F] [InnerProductSpace ℝ F]
    [FiniteDimensional ℝ F]
    (T : F ≃ₗᵢ[ℝ] F) (W : Submodule ℝ F)
    (hW : ∀ x ∈ W, T x ∈ W) :
    ∀ x ∈ Submodule.orthogonal W, T x ∈ Submodule.orthogonal W := by
  have hsurj := invariant_submodule_image_surj T W hW
  intro x hx
  rw [Submodule.mem_orthogonal]
  intro w hw
  obtain ⟨y, hyW, rfl⟩ := hsurj w hw
  rw [T.inner_map_map]
  exact (Submodule.mem_orthogonal W x).mp hx y hyW

/-- Every endomorphism of a 1-dimensional real inner product space is a scalar multiple
of the identity. -/
theorem endo_finrank_one_eq_smul_id
    {F : Type*} [NormedAddCommGroup F] [InnerProductSpace ℝ F]
    [FiniteDimensional ℝ F]
    (f : F →ₗ[ℝ] F) (hfin : Module.finrank ℝ F = 1) :
    ∃ c : ℝ, f = c • LinearMap.id := by
  have hpos : 0 < Module.finrank ℝ F := hfin ▸ Nat.one_pos
  obtain ⟨v, hv0⟩ : ∃ v : F, v ≠ 0 := by
    have := Module.nontrivial_of_finrank_pos hpos; exact exists_ne 0
  have htop : ℝ ∙ v = ⊤ := (finrank_eq_one_iff_of_nonzero v hv0).mp hfin
  have hspan : ∀ w : F, ∃ c : ℝ, c • v = w := fun w => by
    have hmem : w ∈ (ℝ ∙ v) := htop ▸ Submodule.mem_top
    exact Submodule.mem_span_singleton.mp hmem
  obtain ⟨c, hc⟩ := hspan (f v)
  refine ⟨c, LinearMap.ext fun x => ?_⟩
  obtain ⟨r, hr⟩ := hspan x
  simp only [LinearMap.smul_apply, LinearMap.id_apply]
  rw [← hr, map_smul, ← hc, smul_smul, smul_smul, mul_comm]

/-- In a 1-dimensional real inner product space, every endomorphism `f` acts on each
element as scalar multiplication by `LinearMap.det f`. -/
theorem endo_eq_det_smul_of_finrank_one
    {F : Type*} [NormedAddCommGroup F] [InnerProductSpace ℝ F]
    [FiniteDimensional ℝ F]
    (f : F →ₗ[ℝ] F) (hfin : Module.finrank ℝ F = 1) (x : F) :
    f x = (LinearMap.det f) • x := by
  have h1 := endo_finrank_one_eq_smul_id f hfin
  obtain ⟨c, hc⟩ := h1
  rw [hc, LinearMap.det_smul, LinearMap.det_id, hfin, pow_one, mul_one]
  simp [LinearMap.smul_apply]

/-- In a real inner product space with `finrank ≤ 1`, every endomorphism `f` acts as
multiplication by `LinearMap.det f`. The proof splits on `finrank = 0` (where `F` is a
singleton and both sides vanish) and `finrank = 1` (handled by
`endo_eq_det_smul_of_finrank_one`). -/
theorem endo_finrank_le_one_eq_det_smul
    {F : Type*} [NormedAddCommGroup F] [InnerProductSpace ℝ F]
    [FiniteDimensional ℝ F]
    (f : F →ₗ[ℝ] F) (hfin : Module.finrank ℝ F ≤ 1) (x : F) :
    f x = (LinearMap.det f) • x := by
  rcases Nat.eq_zero_or_pos (Module.finrank ℝ F) with h0 | hpos
  · have hsub : Subsingleton F := Module.finrank_zero_iff.mp h0
    rw [Subsingleton.elim x 0, map_zero, smul_zero]
  · have h1 : Module.finrank ℝ F = 1 := le_antisymm hfin hpos
    exact endo_eq_det_smul_of_finrank_one f h1 x

/-- If `T` is a linear isometry of `EuclideanSpace ℝ (Fin n)`, `W` is a `T`-invariant
submodule with `finrank ℝ W ≤ 1`, and the restriction `T|_W` has determinant `1`, then
`T` fixes every point of `W`. -/
theorem det_one_isometry_finrank_le_one_submodule_eq_id
    {n : ℕ} (T : EuclideanSpace ℝ (Fin n) ≃ₗᵢ[ℝ] EuclideanSpace ℝ (Fin n))
    (W : Submodule ℝ (EuclideanSpace ℝ (Fin n)))
    (hinv : ∀ x ∈ W, T x ∈ W)
    (hr : Module.finrank ℝ W ≤ 1)
    (hdet : LinearMap.det
      ((T : EuclideanSpace ℝ (Fin n) →ₗ[ℝ] EuclideanSpace ℝ (Fin n)).restrict hinv) = 1) :
    ∀ x ∈ W, T x = x := by
  intro x hx
  have h := endo_finrank_le_one_eq_det_smul
    ((T : EuclideanSpace ℝ (Fin n) →ₗ[ℝ] EuclideanSpace ℝ (Fin n)).restrict hinv) hr ⟨x, hx⟩
  rw [hdet, one_smul] at h
  have h2 := congrArg Subtype.val h
  simpa [LinearMap.restrict_apply] using h2

/-- For a non-trivial linear isometry `T : E ≃ₗᵢ[ℝ] E` with `det T = 1`, the
$1$-eigenspace `ker(T - id)` has `finrank ≤ 1`.

The proof proceeds by contrapositive: assuming `finrank ≥ 2`, the orthogonal complement
`V⊥` has `finrank ≤ 1`. The determinant splits as
`det(T|_V) · det(T|_{V⊥}) = det T = 1`. Since `T` is the identity on `V`, we get
`det(T|_{V⊥}) = 1`, so by `det_one_isometry_finrank_le_one_submodule_eq_id`, `T` fixes
`V⊥` pointwise. But then `V⊥ ≤ V`, forcing `V⊥ = ⊥` and `V = ⊤`, i.e. `T = refl`,
contradicting `hne`. -/
theorem rotation_eigenspace_one_finrank_le_one
    (T : E ≃ₗᵢ[ℝ] E)
    (hdet : LinearMap.det (T.toLinearEquiv.toLinearMap) = 1)
    (hne : T ≠ LinearIsometryEquiv.refl ℝ E) :
    Module.finrank ℝ (LinearMap.ker (T.toLinearEquiv.toLinearMap - LinearMap.id)) ≤ 1 := by
  set L := T.toLinearEquiv.toLinearMap with hL
  have hmem : ∀ x : E, x ∈ LinearMap.ker (L - LinearMap.id) ↔ T x = x := by
    intro x
    rw [LinearMap.mem_ker, LinearMap.sub_apply, LinearMap.id_apply, sub_eq_zero]
    constructor <;> intro h <;> simpa [hL] using h
  by_contra hcon
  rw [not_le] at hcon
  set V := LinearMap.ker (L - LinearMap.id) with hV
  have hVinv : ∀ x ∈ V, T x ∈ V := by
    intro x hx
    rw [(hmem x).mp hx]
    exact hx
  have hPinv : ∀ x ∈ Vᗮ, T x ∈ Vᗮ := isometry_fixed_complement_invariant T V hVinv
  have hbot : V ⊓ Vᗮ = ⊥ := Submodule.inf_orthogonal_eq_bot V
  have htop : V ⊔ Vᗮ = ⊤ := Submodule.sup_orthogonal_of_hasOrthogonalProjection
  have hsplit := det_eq_prod_det_restrict_invariant L V Vᗮ hVinv hPinv hbot htop
  have hdetV : LinearMap.det (L.restrict hVinv) = 1 := by
    have hid : L.restrict hVinv = LinearMap.id := by
      refine LinearMap.ext fun y => ?_
      apply Subtype.ext
      have hy : T (y : E) = (y : E) := (hmem _).mp y.2
      simp only [LinearMap.restrict_apply, LinearMap.id_coe, id_eq]
      simpa [hL] using hy
    rw [hid, LinearMap.det_id]
  have hdetP : LinearMap.det (L.restrict hPinv) = 1 := by
    rw [hdetV, hdet] at hsplit; linarith
  have hPle : Module.finrank ℝ (Vᗮ) ≤ 1 := by
    have hadd := Submodule.finrank_add_finrank_orthogonal (K := V)
    have h3 : Module.finrank ℝ E = 3 := finrank_euclideanSpace_fin
    omega
  have hfix : ∀ x ∈ Vᗮ, T x = x :=
    det_one_isometry_finrank_le_one_submodule_eq_id T Vᗮ hPinv hPle hdetP
  have hsub : Vᗮ ≤ V := fun x hx => (hmem x).mpr (hfix x hx)
  have hVperp_bot : Vᗮ = ⊥ := by
    rw [eq_bot_iff, ← hbot]
    exact le_inf hsub le_rfl
  have hVtop : V = ⊤ := Submodule.orthogonal_eq_bot_iff.mp hVperp_bot
  apply hne
  refine LinearIsometryEquiv.ext (fun x => ?_)
  have hxV : x ∈ V := by rw [hVtop]; exact Submodule.mem_top
  rw [(hmem x).mp hxV]
  rfl

/-- **Rotation fixed-point finiteness**: for a non-trivial orientation-preserving
isometry `T : E ≃ₗᵢ[ℝ] E` (i.e. `det T = 1` and `T ≠ refl`), the fixed-point set on
the unit sphere is finite. The fixed-point set is contained in the intersection of the
unit sphere with the $1$-eigenspace `ker(T - id)`, which has `finrank ≤ 1` by
`rotation_eigenspace_one_finrank_le_one`; such intersections are finite by
`sphere_inter_finrank_le_one_finite`. -/
theorem rotation_fixed_set_on_sphere_finite
    (T : E ≃ₗᵢ[ℝ] E)
    (hdet : LinearMap.det (T.toLinearEquiv.toLinearMap) = 1)
    (hT : T ≠ LinearIsometryEquiv.refl ℝ E) :
    {x ∈ Metric.sphere (0 : E) 1 | T x = x}.Finite := by
  set V := LinearMap.ker (T.toLinearEquiv.toLinearMap - LinearMap.id)
  have hV : Module.finrank ℝ V ≤ 1 :=
    rotation_eigenspace_one_finrank_le_one T hdet hT
  apply Set.Finite.subset (sphere_inter_finrank_le_one_finite V hV)
  rintro x ⟨hx_sph, hTx⟩
  refine ⟨hx_sph, ?_⟩
  rw [LinearMap.mem_ker, LinearMap.sub_apply, LinearMap.id_apply, sub_eq_zero]
  exact hTx

end Library.Geometry.BanachTarski.FixedSetLemmas
