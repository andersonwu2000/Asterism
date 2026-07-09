import Mathlib.AlgebraicTopology.SimplexCategory.Basic
import Mathlib.Analysis.Convex.Contractible
import Mathlib.Analysis.InnerProductSpace.PiL2
import Mathlib.Data.Real.Hom
import Mathlib.Data.Real.StarOrdered
import Mathlib.RingTheory.Flat.TorsionFree
import Mathlib.RingTheory.TotallySplit

/-!
# The equatorial band of a sphere deformation retracts onto the sphere it separates

For `n : ℕ`, the sphere `S^{n+1} ⊆ E^{n+2}` splits along its last coordinate into a north pole,
a south pole, an equatorial "band" `{x | x_last ≠ ±1}`, and the equator `{x | x_last = 0}` itself.
This file shows that the band is homotopy equivalent both to `S^n × (-1, 1)` and, collapsing the
interval factor, to `S^n`, matching the equatorial sphere.

The band is reached from `S^{n+1}` in two stages: first the last coordinate is peeled off via a
linear coordinate split of the ambient `EuclideanSpace`, landing in a "cylinder"
`{q : E^{n+1} × ℝ | ‖q.1‖ ^ 2 + q.2 ^ 2 = 1 ∧ q.2 ≠ ±1}`; then the cylinder is radially normalized
onto `S^n × (-1, 1)`.

## Main definitions

* `band_coord_split`: the equatorial band is homeomorphic to the cylinder-band.
* `band_homeo_sphere_prod_interval`: the equatorial band is homeomorphic to `S^n × (-1, 1)`.
* `band_hequiv_lower_sphere`: the equatorial band is homotopy equivalent to `S^n`.
* `sphere_equator_homeo`: the equator of `S^{n+1}` is homeomorphic to `S^n`.
* `sphere_band_equator_hequiv`: the equatorial band is homotopy equivalent to the equator.

## Main statements

* `cyl_fwd_mem_sphere`, `cyl_inv_mem_domain`, `cyl_left_inv_smul`, `cyl_norm_ne_zero`,
  `cyl_right_inv_smul`, `cyl_snd_mem_ioo`, `band_flat_predicate_iff`: auxiliary lemmas underlying
  the cylinder/sphere correspondence used to build `cyl_normalize_to_sphere_prod` and
  `band_flat_to_cyl`.
-/

namespace Library.AlgebraicTopology.SphereHomology.SphereEquatorCylinderBand

variable (n : ℕ)

/-- The homotopy equivalence `S^n × (-1, 1) ≃ₕ S^n` obtained by collapsing the contractible
interval factor. The open interval `(-1, 1)` is convex, hence contractible, so it is homotopy
equivalent to `Unit`; `ContinuousMap.HomotopyEquiv.prodCongr` with the identity on the sphere gives
`S^n × (-1, 1) ≃ₕ S^n × Unit`, and `Homeomorph.prodUnique` projects off the `Unit` factor to
land on `S^n`. -/
noncomputable def sphere_prod_interval_hequiv_sphere :
    ContinuousMap.HomotopyEquiv
      ((Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+1))) 1) × ↥(Set.Ioo (-1 : ℝ) 1))
      (Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+1))) 1) := by
  have hc : ContractibleSpace ↥(Set.Ioo (-1 : ℝ) 1) :=
    (convex_Ioo (-1:ℝ) 1).contractibleSpace (Set.nonempty_Ioo.mpr (by norm_num))
  have hI : ContinuousMap.HomotopyEquiv ↥(Set.Ioo (-1 : ℝ) 1) Unit :=
    Classical.choice (ContractibleSpace.hequiv_unit _)
  exact ((ContinuousMap.HomotopyEquiv.refl _).prodCongr hI).trans
    (Homeomorph.prodUnique _ _).toHomotopyEquiv

/-- The coordinate hyperplane `ker (proj (Fin.last (n+1)))` of `E^{n+2}` is linearly isometric to
`E^{n+1}`, via `x ↦ Fin.snoc x 0` (appending a zero last coordinate). The isometry `f` preserves
the norm since the appended coordinate is `0`; its range is identified with the kernel using
`x_last = 0 ↔ x = Fin.snoc (Fin.init x) 0`, and the result transports via
`f.equivRange.trans (LinearIsometryEquiv.ofEq ..)`. -/
noncomputable def equator_hyperplane_lie :
    EuclideanSpace ℝ (Fin (n+1)) ≃ₗᵢ[ℝ]
      (LinearMap.ker ((EuclideanSpace.proj (Fin.last (n+1)) :
        EuclideanSpace ℝ (Fin (n+2)) →L[ℝ] ℝ) :
          EuclideanSpace ℝ (Fin (n+2)) →ₗ[ℝ] ℝ)) := by
  let f : EuclideanSpace ℝ (Fin (n+1)) →ₗᵢ[ℝ] EuclideanSpace ℝ (Fin (n+2)) :=
    { toFun := fun x ↦ WithLp.toLp 2 (Fin.snoc (α := fun _ ↦ ℝ) (WithLp.ofLp x) 0)
      map_add' := by
        intro x y
        ext i
        refine Fin.lastCases ?_ ?_ i <;> simp
      map_smul' := by
        intro c x
        ext i
        refine Fin.lastCases ?_ ?_ i <;> simp
      norm_map' := by
        intro x
        rw [EuclideanSpace.norm_eq, EuclideanSpace.norm_eq, Fin.sum_univ_castSucc]
        simp }
  have hrange : LinearMap.range f.toLinearMap =
      LinearMap.ker ((EuclideanSpace.proj (Fin.last (n+1)) :
        EuclideanSpace ℝ (Fin (n+2)) →L[ℝ] ℝ) :
          EuclideanSpace ℝ (Fin (n+2)) →ₗ[ℝ] ℝ) := by
    ext x
    simp only [LinearMap.mem_range, LinearMap.mem_ker]
    constructor
    · rintro ⟨y, rfl⟩
      simp [f]
    · intro hx
      have hlast : WithLp.ofLp x (Fin.last (n+1)) = 0 := hx
      refine ⟨WithLp.toLp 2 (Fin.init (WithLp.ofLp x)), ?_⟩
      change WithLp.toLp 2 (Fin.snoc (WithLp.ofLp
        (WithLp.toLp 2 (Fin.init (WithLp.ofLp x)))) 0) = x
      rw [WithLp.ofLp_toLp, ← hlast, Fin.snoc_init_self, WithLp.toLp_ofLp]
  exact f.equivRange.trans (LinearIsometryEquiv.ofEq _ _ hrange)

/-- The equator `{x | x_last = 0}` of the sphere `S^{n+1} ⊆ E^{n+2}` is homeomorphic to the unit
sphere of the coordinate hyperplane `ker (proj (Fin.last (n+1)))`: both consist of the unit
vectors of `E^{n+2}` with last coordinate `0`, and the underlying map is the identity on the
vector — membership in the kernel is `proj last v = v_last = 0`, and the norm transports through
the submodule coercion defeq. -/
noncomputable def equator_ker_sphere_homeo :
    ↥{x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+2))) 1 | x.1 (Fin.last (n+1)) = 0} ≃ₜ
      Metric.sphere (0 : (LinearMap.ker ((EuclideanSpace.proj (Fin.last (n+1)) :
        EuclideanSpace ℝ (Fin (n+2)) →L[ℝ] ℝ) :
          EuclideanSpace ℝ (Fin (n+2)) →ₗ[ℝ] ℝ))) 1 :=
  { toFun := fun p ↦ ⟨⟨p.1.1, by
        have h := p.2
        simp only [Set.mem_setOf_eq] at h
        rw [LinearMap.mem_ker, ContinuousLinearMap.coe_coe]
        simpa using h⟩, by
        have h := p.1.2
        rw [mem_sphere_zero_iff_norm] at h
        rw [mem_sphere_zero_iff_norm]
        exact h⟩
    invFun := fun q ↦ ⟨⟨q.1.1, by
        have h := q.2
        rw [mem_sphere_zero_iff_norm] at h
        rw [mem_sphere_zero_iff_norm]
        exact h⟩, by
        have hk := q.1.2
        rw [LinearMap.mem_ker, ContinuousLinearMap.coe_coe] at hk
        exact hk⟩
    left_inv := fun p ↦ by rfl
    right_inv := fun q ↦ by rfl
    continuous_toFun := by
      apply Continuous.subtype_mk
      apply Continuous.subtype_mk
      exact continuous_subtype_val.comp continuous_subtype_val
    continuous_invFun := by
      apply Continuous.subtype_mk
      apply Continuous.subtype_mk
      exact continuous_subtype_val.comp continuous_subtype_val }

/-- The equator `{x | x_last = 0}` of `S^{n+1}` is homeomorphic to `S^n`. This composes the
geometric heart `equator_hyperplane_lie` — a linear *isometry* equiv `E^{n+1} ≃ₗᵢ ker (proj last)`
onto the coordinate hyperplane, which bundles its own continuity — with
`equator_ker_sphere_homeo`, the reassociation of the nested sphere-subtype into the unit sphere of
that hyperplane, restricting the isometry to unit spheres via `Homeomorph.subtype` (isometries
preserve norm, so the sphere predicate transports and `simp` discharges the iff). -/
noncomputable def sphere_equator_homeo :
    ↥{x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+2))) 1 | x.1 (Fin.last (n+1)) = 0} ≃ₜ
      Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+1))) 1 := by
  refine (equator_ker_sphere_homeo n).trans ?_
  refine Homeomorph.subtype (equator_hyperplane_lie n).symm.toHomeomorph ?_
  intro x
  simp

/-- Flatten the nested sphere-subtype `{x : S^{n+1} | x_last ≠ ±1}` into the flat ambient subtype
`{x : E^{n+2} | ‖x‖ = 1 ∧ x_last ≠ ±1}`. The underlying map is the identity on the ambient vector,
so no linear isometry is needed: reassociate `⟨⟨v, hv⟩, hcond⟩ ↔ ⟨v, hv, hcond⟩` with
`left_inv`/`right_inv := rfl`, and prove continuity of both directions by stacking
`Continuous.subtype_mk` over `subtype_val`. -/
def band_subtype_flatten :
    (↥{x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+2))) 1 |
        x.1 (Fin.last (n+1)) ≠ 1 ∧ x.1 (Fin.last (n+1)) ≠ -1}) ≃ₜ
      (↥{x : EuclideanSpace ℝ (Fin (n+2)) | x ∈ Metric.sphere 0 1 ∧
        x (Fin.last (n+1)) ≠ 1 ∧ x (Fin.last (n+1)) ≠ -1}) :=
  { toFun := fun p ↦ ⟨p.1.1, p.1.2, p.2.1, p.2.2⟩
    invFun := fun q ↦ ⟨⟨q.1, q.2.1⟩, q.2.2.1, q.2.2.2⟩
    left_inv := fun _ ↦ rfl
    right_inv := fun _ ↦ rfl
    continuous_toFun := by
      apply Continuous.subtype_mk
      exact continuous_subtype_val.comp continuous_subtype_val
    continuous_invFun := by
      apply Continuous.subtype_mk
      apply Continuous.subtype_mk
      exact continuous_subtype_val }

/-- Normalizing `u` by its norm lands on the unit sphere: from `‖u‖ ^ 2 + t ^ 2 = 1` with
`t ≠ ±1` we get `‖u‖ ≠ 0` (via `sq_ne_one_iff`), then
`‖‖u‖⁻¹ • u‖ = ‖u‖⁻¹ * ‖u‖ = 1` (`norm_smul` + `inv_mul_cancel₀`). -/
theorem cyl_fwd_mem_sphere (u : EuclideanSpace ℝ (Fin (n + 1))) (t : ℝ)
    (h : ‖u‖ ^ 2 + t ^ 2 = 1) (h1 : t ≠ 1) (h2 : t ≠ -1) :
    (‖u‖)⁻¹ • u ∈ Metric.sphere (0 : EuclideanSpace ℝ (Fin (n + 1))) 1 := by
  have hu : ‖u‖ ≠ 0 := fun h0 ↦ (sq_ne_one_iff.mpr ⟨h1, h2⟩) (by simpa [h0] using h)
  simp [mem_sphere_iff_norm, norm_smul, inv_mul_cancel₀ hu]

/-- `norm_smul` + `Real.sq_sqrt` place `(√(1 - t ^ 2) • y, t)` back on the cylinder
`{q | ‖q.1‖ ^ 2 + q.2 ^ 2 = 1 ∧ q.2 ≠ ±1}`, using `‖y‖ = 1` and `t ∈ (-1, 1)` to give
`1 - t ^ 2 ≥ 0`. -/
theorem cyl_inv_mem_domain (y : EuclideanSpace ℝ (Fin (n + 1))) (t : ℝ)
    (hy : y ∈ Metric.sphere (0 : EuclideanSpace ℝ (Fin (n + 1))) 1)
    (ht : t ∈ Set.Ioo (-1 : ℝ) 1) :
    (Real.sqrt (1 - t ^ 2) • y, t) ∈ {q : EuclideanSpace ℝ (Fin (n + 1)) × ℝ |
      ‖q.1‖ ^ 2 + q.2 ^ 2 = 1 ∧ q.2 ≠ 1 ∧ q.2 ≠ -1} := by
  obtain ⟨ht1, ht2⟩ := ht
  have hy1 : ‖y‖ = 1 := by simpa [Metric.mem_sphere, dist_zero_right] using hy
  have h1t2 : (0:ℝ) ≤ 1 - t ^ 2 := by nlinarith
  refine ⟨?_, by linarith, by linarith⟩
  simp [norm_smul, Real.norm_eq_abs, abs_of_nonneg (Real.sqrt_nonneg (1 - t ^ 2)), hy1,
    Real.sq_sqrt h1t2]

/-- `√(1 - t ^ 2) = ‖u‖` (from `h`), then `smul_smul` + `mul_inv_cancel₀` collapses the
round-trip. -/
theorem cyl_left_inv_smul (u : EuclideanSpace ℝ (Fin (n + 1))) (t : ℝ)
    (h : ‖u‖ ^ 2 + t ^ 2 = 1) (h1 : t ≠ 1) (h2 : t ≠ -1) :
    Real.sqrt (1 - t ^ 2) • ((‖u‖)⁻¹ • u) = u := by
  have ht2 : t ^ 2 ≠ 1 := sq_ne_one_iff.mpr ⟨h1, h2⟩
  have hu2 : ‖u‖ ^ 2 = 1 - t ^ 2 := by linarith
  have hne : ‖u‖ ≠ 0 := by
    intro h0
    exact ht2 (by nlinarith)
  have hsqrt : Real.sqrt (1 - t ^ 2) = ‖u‖ := by rw [← hu2]; exact Real.sqrt_sq (norm_nonneg u)
  rw [hsqrt, smul_smul, mul_inv_cancel₀ hne, one_smul]

/-- On the cylinder `‖u‖ ^ 2 + t ^ 2 = 1` with `t ≠ ±1`, the vector `u` is nonzero. -/
theorem cyl_norm_ne_zero (u : EuclideanSpace ℝ (Fin (n + 1))) (t : ℝ)
    (h : ‖u‖ ^ 2 + t ^ 2 = 1) (h1 : t ≠ 1) (h2 : t ≠ -1) :
    ‖u‖ ≠ 0 := by grind

/-- Right inverse of the cylinder radial-normalization map: `‖r • y‖ = r` for
`r = √(1 - t ^ 2) > 0` and `‖y‖ = 1` (`norm_smul` + `abs_of_pos`), so
`(‖r • y‖)⁻¹ • (r • y) = (r⁻¹ * r) • y = y` via `smul_smul` + `inv_mul_cancel₀`. -/
theorem cyl_right_inv_smul (y : EuclideanSpace ℝ (Fin (n + 1))) (t : ℝ)
    (hy : y ∈ Metric.sphere (0 : EuclideanSpace ℝ (Fin (n + 1))) 1)
    (ht : t ∈ Set.Ioo (-1 : ℝ) 1) :
    (‖Real.sqrt (1 - t ^ 2) • y‖)⁻¹ • (Real.sqrt (1 - t ^ 2) • y) = y := by
  have ht2 : t ^ 2 < 1 := by nlinarith [ht.1, ht.2]
  have hr : 0 < Real.sqrt (1 - t ^ 2) := Real.sqrt_pos.mpr (by linarith)
  have hy' : ‖y‖ = 1 := by simpa using hy
  have hrnorm : ‖Real.sqrt (1 - t ^ 2) • y‖ = Real.sqrt (1 - t ^ 2) := by
    rw [norm_smul, Real.norm_eq_abs, abs_of_pos hr, hy', mul_one]
  rw [smul_smul, hrnorm, inv_mul_cancel₀ hr.ne', one_smul]

/-- `sq_le_one_iff_abs_le_one` plus the strict inequalities from `t ≠ ±1`: `‖u‖ ^ 2 + t ^ 2 = 1`
with `‖u‖ ^ 2 ≥ 0` gives `t ^ 2 ≤ 1`, hence `|t| ≤ 1`; the excluded endpoints `t ≠ 1`, `t ≠ -1`
upgrade the non-strict bounds to `t ∈ (-1, 1)`. -/
theorem cyl_snd_mem_ioo (u : EuclideanSpace ℝ (Fin (n + 1))) (t : ℝ)
    (h : ‖u‖ ^ 2 + t ^ 2 = 1) (h1 : t ≠ 1) (h2 : t ≠ -1) :
    t ∈ Set.Ioo (-1 : ℝ) 1 := by
  have hu2 : (0:ℝ) ≤ ‖u‖ ^ 2 := sq_nonneg _
  have ht2 : t ^ 2 ≤ 1 := by nlinarith
  have habs : -1 ≤ t ∧ t ≤ 1 := abs_le.mp ((sq_le_one_iff_abs_le_one t).mp ht2)
  exact ⟨lt_of_le_of_ne habs.1 (Ne.symm h2), lt_of_le_of_ne habs.2 h1⟩

/-- The cylinder `{q : E^{n+1} × ℝ | ‖q.1‖ ^ 2 + q.2 ^ 2 = 1 ∧ q.2 ≠ ±1}` is homeomorphic to
`S^n × (-1, 1)`, via radial normalization `(u, t) ↦ (‖u‖⁻¹ • u, t)` in the forward direction and
rescaling `(y, t) ↦ (√(1 - t ^ 2) • y, t)` in the inverse direction. -/
noncomputable def cyl_normalize_to_sphere_prod :
    (↥{q : EuclideanSpace ℝ (Fin (n+1)) × ℝ |
        ‖q.1‖ ^ 2 + q.2 ^ 2 = 1 ∧ q.2 ≠ 1 ∧ q.2 ≠ -1}) ≃ₜ
      (Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+1))) 1) × ↥(Set.Ioo (-1 : ℝ) 1) :=
  { toFun := fun p ↦
      (⟨(‖p.1.1‖)⁻¹ • p.1.1,
          cyl_fwd_mem_sphere n p.1.1 p.1.2 p.2.1 p.2.2.1 p.2.2.2⟩,
        ⟨p.1.2, cyl_snd_mem_ioo n p.1.1 p.1.2 p.2.1 p.2.2.1 p.2.2.2⟩)
    invFun := fun q ↦
      ⟨(Real.sqrt (1 - (q.2.1)^2) • q.1.1, q.2.1),
        cyl_inv_mem_domain n q.1.1 q.2.1 q.1.2 q.2.2⟩
    left_inv := fun p ↦ by
      refine Subtype.ext (Prod.ext ?_ ?_)
      · exact cyl_left_inv_smul n p.1.1 p.1.2 p.2.1 p.2.2.1 p.2.2.2
      · rfl
    right_inv := fun q ↦ by
      refine Prod.ext (Subtype.ext ?_) rfl
      exact cyl_right_inv_smul n q.1.1 q.2.1 q.1.2 q.2.2
    continuous_toFun := by
      have hbase : Continuous (fun p : ↥{q : EuclideanSpace ℝ (Fin (n+1)) × ℝ |
          ‖q.1‖ ^ 2 + q.2 ^ 2 = 1 ∧ q.2 ≠ 1 ∧ q.2 ≠ -1} ↦ p.1.1) :=
        continuous_fst.comp continuous_subtype_val
      refine Continuous.prodMk (Continuous.subtype_mk ?_ _) (Continuous.subtype_mk ?_ _)
      · exact ((continuous_norm.comp hbase).inv₀
          (fun p ↦ cyl_norm_ne_zero n p.1.1 p.1.2 p.2.1 p.2.2.1 p.2.2.2)).smul hbase
      · exact continuous_snd.comp continuous_subtype_val
    continuous_invFun := by
      refine Continuous.subtype_mk (Continuous.prodMk ?_ ?_) _
      · have ht : Continuous (fun q : (Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+1))) 1) ×
            ↥(Set.Ioo (-1 : ℝ) 1) ↦ q.2.1) := continuous_subtype_val.comp continuous_snd
        have hy : Continuous (fun q : (Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+1))) 1) ×
            ↥(Set.Ioo (-1 : ℝ) 1) ↦ q.1.1) := continuous_subtype_val.comp continuous_fst
        exact (Real.continuous_sqrt.comp (continuous_const.sub (ht.pow 2))).smul hy
      · exact continuous_subtype_val.comp continuous_snd }

/-- Sphere membership rewritten as a norm-squared split via `EuclideanSpace.norm_sq_eq` +
`Fin.sum_univ_castSucc`, closed with `sq_eq_sq₀` (both sides nonneg) to move between `‖x‖ = 1` and
`‖x‖ ^ 2 = 1 ^ 2`: `x` lies on the unit sphere of `E^{n+2}` and avoids the poles `x_last = ±1` if
and only if the norm of its first `n + 1` coordinates squared plus `x_last ^ 2` equals `1`, with
the same pole exclusion. -/
theorem band_flat_predicate_iff (x : EuclideanSpace ℝ (Fin (n + 2))) :
    (x ∈ Metric.sphere 0 1 ∧ x (Fin.last (n + 1)) ≠ 1 ∧ x (Fin.last (n + 1)) ≠ -1) ↔
      (‖(WithLp.toLp 2 (fun i : Fin (n + 1) ↦ x i.castSucc) :
            EuclideanSpace ℝ (Fin (n + 1)))‖ ^ 2 + (x (Fin.last (n + 1))) ^ 2 = 1 ∧
        x (Fin.last (n + 1)) ≠ 1 ∧ x (Fin.last (n + 1)) ≠ -1) := by
  have hkey : x ∈ Metric.sphere (0 : EuclideanSpace ℝ (Fin (n + 2))) 1 ↔
      ‖(WithLp.toLp 2 (fun i : Fin (n + 1) ↦ x i.castSucc) :
            EuclideanSpace ℝ (Fin (n + 1)))‖ ^ 2 + (x (Fin.last (n + 1))) ^ 2 = 1 := by
    rw [mem_sphere_zero_iff_norm, ← sq_eq_sq₀ (norm_nonneg x) (zero_le_one),
      EuclideanSpace.norm_sq_eq, EuclideanSpace.norm_sq_eq, Fin.sum_univ_castSucc]
    simp [Real.norm_eq_abs, sq_abs]
  rw [hkey]

/-- Flatten the ambient last-coordinate split into a cylinder-band homeomorphism.
`e : E^{n+2} ≃ₜ E^{n+1} × ℝ` splits off the last coordinate (first block = the first `n + 1`
coordinates via `castSucc`, second = the last coordinate); it is a concrete `Homeomorph`
(continuity by `fun_prop`, inverse via `Fin.snoc`). Restricting `e` through `Homeomorph.subtype`
with `band_flat_predicate_iff` (the pointwise membership equivalence: `‖x‖ = 1 ↔
‖first block‖ ^ 2 + last ^ 2 = 1`, the `≠ ±1` conditions transport verbatim as `e`'s second
coordinate is literally the last coordinate) yields the goal. -/
noncomputable def band_flat_to_cyl :
    (↥{x : EuclideanSpace ℝ (Fin (n+2)) | x ∈ Metric.sphere 0 1 ∧
        x (Fin.last (n+1)) ≠ 1 ∧ x (Fin.last (n+1)) ≠ -1}) ≃ₜ
      (↥{q : EuclideanSpace ℝ (Fin (n+1)) × ℝ |
        ‖q.1‖ ^ 2 + q.2 ^ 2 = 1 ∧ q.2 ≠ 1 ∧ q.2 ≠ -1}) :=
  let e : EuclideanSpace ℝ (Fin (n+2)) ≃ₜ EuclideanSpace ℝ (Fin (n+1)) × ℝ :=
    { toFun := fun x ↦ (WithLp.toLp 2 (fun i : Fin (n+1) ↦ x i.castSucc),
        x (Fin.last (n+1)))
      invFun := fun p ↦ WithLp.toLp 2 (Fin.snoc (WithLp.ofLp p.1) p.2)
      left_inv := by
        intro x
        ext i
        refine Fin.lastCases ?_ (fun j ↦ ?_) i
        · simp [Fin.snoc_last]
        · simp [Fin.snoc_castSucc]
      right_inv := by
        intro p
        ext
        · simp
        · simp
      continuous_toFun := by fun_prop
      continuous_invFun := by fun_prop }
  e.subtype (fun x ↦ band_flat_predicate_iff n x)

/-- The equatorial band `{x : S^{n+1} | x_last ≠ ±1}` is homeomorphic to the cylinder-band
`{q : E^{n+1} × ℝ | ‖q.1‖ ^ 2 + q.2 ^ 2 = 1 ∧ q.2 ≠ ±1}`. This flattens the sphere-subtype nesting
(`band_subtype_flatten`, pure subtype/topology plumbing) and then applies the geometric heart
`band_flat_to_cyl` — a single bundled homeomorphism built from the last-coordinate linear split. -/
noncomputable def band_coord_split :
    (↥{x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+2))) 1 |
        x.1 (Fin.last (n+1)) ≠ 1 ∧ x.1 (Fin.last (n+1)) ≠ -1}) ≃ₜ
      (↥{q : EuclideanSpace ℝ (Fin (n+1)) × ℝ |
        ‖q.1‖ ^ 2 + q.2 ^ 2 = 1 ∧ q.2 ≠ 1 ∧ q.2 ≠ -1}) :=
  (band_subtype_flatten n).trans (band_flat_to_cyl n)

/-- Factor the equatorial band's homeomorphism with `S^n × (-1, 1)` through a linear-isometry
coordinate split followed by a fibrewise normalization, composed with `.trans`.
`band_coord_split` reshuffles the ambient `EuclideanSpace ℝ (Fin (n+2))` into
`EuclideanSpace ℝ (Fin (n+1)) × ℝ` (last coordinate peeled off), carrying the unit-sphere
constraint `‖x‖ = 1` to `‖q.1‖ ^ 2 + q.2 ^ 2 = 1` and the pole-exclusion `x_last ≠ ±1` to
`q.2 ≠ ±1` — pure index gymnastics, no analysis. `cyl_normalize_to_sphere_prod` then does the
analytic heart: send `(u, t)` on that cylinder to `(u / ‖u‖, t)`, well-defined since `t ≠ ±1`
forces `‖u‖ ^ 2 = 1 - t ^ 2 > 0`, landing on `S^n × (-1, 1)`; its inverse rescales
`(y, t) ↦ (√(1 - t ^ 2) • y, t)`. -/
noncomputable def band_homeo_sphere_prod_interval :
    (↥{x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+2))) 1 |
        x.1 (Fin.last (n+1)) ≠ 1 ∧ x.1 (Fin.last (n+1)) ≠ -1}) ≃ₜ
      (Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+1))) 1) × ↥(Set.Ioo (-1 : ℝ) 1) :=
  (band_coord_split n).trans (cyl_normalize_to_sphere_prod n)

/-- The equatorial band `{x : S^{n+1} | x_last ≠ ±1}` is homotopy equivalent to `S^n`. This
composes `band_homeo_sphere_prod_interval` (band ≃ₜ `S^n × (-1, 1)`, sending `x` to its
normalized equatorial part and its last coordinate) with `sphere_prod_interval_hequiv_sphere`,
the projection `S^n × (-1, 1) ≃ₕ S^n` collapsing the contractible interval factor. -/
noncomputable def band_hequiv_lower_sphere :
    ContinuousMap.HomotopyEquiv
      ↥{x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+2))) 1 |
          x.1 (Fin.last (n+1)) ≠ 1 ∧ x.1 (Fin.last (n+1)) ≠ -1}
      (Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+1))) 1) := by
  have hA := band_homeo_sphere_prod_interval n
  have hB := sphere_prod_interval_hequiv_sphere n
  exact (hA.toHomotopyEquiv).trans hB

/-- **The equatorial band is homotopy equivalent to the equator**: the band
`{x : S^{n+1} | x_last ≠ ±1}` is homotopy equivalent to the equator `{x : S^{n+1} | x_last = 0}`.
This composes `band_hequiv_lower_sphere` (band ≃ₕ `S^n`) with the reverse of the homeomorphism
`sphere_equator_homeo` (equator ≃ₜ `S^n`). -/
noncomputable def sphere_band_equator_hequiv :
    ContinuousMap.HomotopyEquiv
      ↥{x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+2))) 1 |
          x.1 (Fin.last (n+1)) ≠ 1 ∧ x.1 (Fin.last (n+1)) ≠ -1}
      ↥{x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+2))) 1 |
          x.1 (Fin.last (n+1)) = 0} :=
  (band_hequiv_lower_sphere n).trans (sphere_equator_homeo n).toHomotopyEquiv.symm

end Library.AlgebraicTopology.SphereHomology.SphereEquatorCylinderBand
