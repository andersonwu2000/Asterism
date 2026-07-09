import Mathlib.Algebra.Group.Action.Equidecomp
import Mathlib.AlgebraicTopology.SimplexCategory.Basic
import Mathlib.Analysis.Normed.Affine.MazurUlam
import Mathlib.Order.BourbakiWitt
import Mathlib.Order.CompletePartialOrder
import Mathlib.RingTheory.Flat.FaithfullyFlat.Basic
import Mathlib.RingTheory.Flat.TorsionFree
import Mathlib.RingTheory.SimpleRing.Principal
import Library.Geometry.BanachTarski.Defs

/-!
# Cone equidecomposition

This file lifts an equidecomposition `e` between subsets of the unit sphere
`Metric.sphere (0 : E) 1` to an equidecomposition between their respective cone images
`{r • x | r ∈ (0, 1], x ∈ e.source}` and `{r • x | r ∈ (0, 1], x ∈ e.target}` inside `E`.

## Main statements

* `cone_over_sphere_eq_punctured_ball`: the cone over the unit sphere equals the punctured closed
  unit ball `Metric.closedBall 0 1 \ {0}`.
* `cone_lift_equidecomp`: an equidecomposition between subsets of the unit sphere lifts to an
  equidecomposition between their corresponding cones, using the same finite set of isometries.

## Implementation notes

The radial lift sends a nonzero point `y` to `‖y‖ • e (‖y‖⁻¹ • y)`. The key ingredient is
`isometry_fixing_origin_smul_comm`: any isometry fixing the origin commutes with scalar
multiplication (it is in fact real-linear), so the lifted action intertwines correctly with the
group action.
-/

open Library.Geometry.BanachTarski.Defs

namespace Library.Geometry.BanachTarski.ConeEquidecomp

/-- An isometry of a normed space that fixes the origin commutes with scalar multiplication.
This follows from the fact that such an isometry is a real-linear isometry equivalence. -/
theorem isometry_fixing_origin_smul_comm
    (g : E ≃ᵢ E) (hg : g 0 = 0) (r : ℝ) (x : E) :
    g (r • x) = r • g x := by
  have hmap := (g.toRealLinearIsometryEquivOfMapZero hg).map_smul r x
  rw [g.coe_toRealLinearIsometryEquivOfMapZero hg] at hmap
  exact hmap

/-- The cone over the unit sphere, i.e., `{r • x | r ∈ (0, 1], x ∈ Metric.sphere 0 1}`,
equals the punctured closed unit ball `Metric.closedBall 0 1 \ {0}`. -/
theorem cone_over_sphere_eq_punctured_ball :
    { y : E | ∃ r ∈ Set.Ioc (0 : ℝ) 1, ∃ x ∈ Metric.sphere (0 : E) 1, y = r • x }
      = Metric.closedBall (0 : E) 1 \ {0} := by
  ext y
  simp only [Set.mem_setOf_eq, Set.mem_diff, Metric.mem_closedBall, dist_zero_right,
    Metric.mem_sphere, Set.mem_singleton_iff]
  constructor
  · rintro ⟨r, ⟨hr0, hr1⟩, x, hx, rfl⟩
    refine ⟨?_, ?_⟩
    · rw [norm_smul, Real.norm_eq_abs, abs_of_pos hr0, hx, mul_one]; exact hr1
    · exact smul_ne_zero (ne_of_gt hr0) (by rw [← norm_pos_iff, hx]; norm_num)
  · rintro ⟨hy1, hy0⟩
    have hyn : 0 < ‖y‖ := norm_pos_iff.mpr hy0
    refine ⟨‖y‖, ⟨hyn, hy1⟩, ‖y‖⁻¹ • y, ?_, ?_⟩
    · rw [norm_smul, norm_inv, Real.norm_eq_abs, abs_norm,
        inv_mul_cancel₀ (ne_of_gt hyn)]
    · rw [smul_smul, mul_inv_cancel₀ (ne_of_gt hyn), one_smul]

/-- The cone construction distributes over set union: the cone over `A ∪ B` equals the union of
the cones over `A` and `B`. -/
theorem cone_distrib_union (A B : Set E) :
    {y | ∃ r ∈ Set.Ioc (0 : ℝ) 1, ∃ x ∈ A ∪ B, y = r • x}
      = {y | ∃ r ∈ Set.Ioc (0 : ℝ) 1, ∃ x ∈ A, y = r • x}
        ∪ {y | ∃ r ∈ Set.Ioc (0 : ℝ) 1, ∃ x ∈ B, y = r • x} := by
  ext y
  simp only [Set.mem_setOf_eq, Set.mem_union]
  constructor
  · rintro ⟨r, hr, x, hx | hx, hy⟩
    · left; exact ⟨r, hr, x, hx, hy⟩
    · right; exact ⟨r, hr, x, hx, hy⟩
  · rintro (⟨r, hr, x, hx, hy⟩ | ⟨r, hr, x, hx, hy⟩)
    · exact ⟨r, hr, x, Or.inl hx, hy⟩
    · exact ⟨r, hr, x, Or.inr hx, hy⟩

/-- If `A` and `B` are disjoint subsets of the unit sphere, then their cones are disjoint.
The key observation is that `‖r • x‖ = r` for `x` on the unit sphere and `r > 0`, so two cone
points with the same value must have the same radius and hence the same base point. -/
theorem cone_preserves_disjoint (A B : Set E)
    (hA : A ⊆ Metric.sphere (0 : E) 1) (hB : B ⊆ Metric.sphere (0 : E) 1)
    (hdisj : Disjoint A B) :
    Disjoint {y | ∃ r ∈ Set.Ioc (0 : ℝ) 1, ∃ x ∈ A, y = r • x}
             {y | ∃ r ∈ Set.Ioc (0 : ℝ) 1, ∃ x ∈ B, y = r • x} := by
  rw [Set.disjoint_left]
  intro y ⟨r₁, hr₁, x₁, hx₁A, hy₁⟩ ⟨r₂, hr₂, x₂, hx₂B, hy₂⟩
  have hx₁n : ‖x₁‖ = 1 := by
    have := hA hx₁A; rwa [Metric.mem_sphere, dist_zero_right] at this
  have hx₂n : ‖x₂‖ = 1 := by
    have := hB hx₂B; rwa [Metric.mem_sphere, dist_zero_right] at this
  have hr₁pos : (0 : ℝ) < r₁ := hr₁.1
  have hr₂pos : (0 : ℝ) < r₂ := hr₂.1
  have hr₁eq : ‖y‖ = r₁ := by
    rw [hy₁, norm_smul, Real.norm_of_nonneg hr₁pos.le, hx₁n, mul_one]
  have hr₂eq : ‖y‖ = r₂ := by
    rw [hy₂, norm_smul, Real.norm_of_nonneg hr₂pos.le, hx₂n, mul_one]
  have hrr : r₁ = r₂ := hr₁eq.symm.trans hr₂eq
  have hx_eq : x₁ = x₂ := by
    have h : r₁ • x₁ = r₁ • x₂ := hy₁.symm.trans (hrr ▸ hy₂)
    have := congr_arg (r₁⁻¹ • ·) h
    simp only [smul_smul, inv_mul_cancel₀ hr₁pos.ne', one_smul] at this
    exact this
  exact Set.disjoint_left.mp hdisj hx₁A (hx_eq ▸ hx₂B)

/-- The radial cone lift of an equidecomposition is itself an equidecomposition on the source cone.
For each cone point `y = r • x` with `x ∈ e.source`, the decomposition element `g ∈ S` realizing
`e` at `x` also realizes the lifted map at `y`, using `isometry_fixing_origin_smul_comm` to
interchange `g` with scalar multiplication. -/
theorem cone_is_decomp (e : Equidecomp E (E ≃ᵢ E)) (S : Finset (E ≃ᵢ E))
    (hdec : Equidecomp.IsDecompOn e.toFun e.source S) (h0 : ∀ s ∈ S, s 0 = 0)
    (hsrc : e.source ⊆ Metric.sphere (0 : E) 1)
    (_htgt : e.target ⊆ Metric.sphere (0 : E) 1) :
    Equidecomp.IsDecompOn (fun z => ‖z‖ • e.toFun (‖z‖⁻¹ • z))
      {y | ∃ r ∈ Set.Ioc (0 : ℝ) 1, ∃ x ∈ e.source, y = r • x} S := by
  intro y hy
  obtain ⟨r, hr, x, hx, rfl⟩ := hy
  obtain ⟨g, hgS, hgx⟩ := hdec x hx
  refine ⟨g, hgS, ?_⟩
  have hx1 : ‖x‖ = 1 := by
    have h := hsrc hx
    rwa [mem_sphere_zero_iff_norm] at h
  have hrpos : 0 < r := hr.1
  have hnr : ‖r • x‖ = r := by
    rw [norm_smul, hx1, mul_one, Real.norm_eq_abs, abs_of_pos hrpos]
  have hxback : (‖r • x‖)⁻¹ • (r • x) = x := by
    rw [hnr, smul_smul, inv_mul_cancel₀ (ne_of_gt hrpos), one_smul]
  change ‖r • x‖ • e.toFun (‖r • x‖⁻¹ • (r • x)) = g • (r • x)
  rw [hxback, hnr, hgx]
  change r • (g x) = g (r • x)
  rw [isometry_fixing_origin_smul_comm g (h0 g hgS) r x]

/-- The radial lift map `y ↦ ‖y‖ • e (‖y‖⁻¹ • y)` has a left inverse on the source cone,
given by the analogous lift of `e.invFun`. -/
theorem cone_left_inv (e : Equidecomp E (E ≃ᵢ E)) (S : Finset (E ≃ᵢ E))
    (_hdec : Equidecomp.IsDecompOn e.toFun e.source S) (_h0 : ∀ s ∈ S, s 0 = 0)
    (hsrc : e.source ⊆ Metric.sphere (0 : E) 1)
    (htgt : e.target ⊆ Metric.sphere (0 : E) 1) :
    ∀ ⦃y : E⦄, y ∈ {y | ∃ r ∈ Set.Ioc (0 : ℝ) 1, ∃ x ∈ e.source, y = r • x} →
      (fun z => ‖z‖ • e.invFun (‖z‖⁻¹ • z))
        ((fun z => ‖z‖ • e.toFun (‖z‖⁻¹ • z)) y) = y := by
  intro y hy
  obtain ⟨r, hr, x, hx, rfl⟩ := hy
  simp only []
  have hxnorm : ‖x‖ = 1 := by
    have := hsrc hx; rwa [Metric.mem_sphere, dist_zero_right] at this
  have hetgnorm : ‖e.toFun x‖ = 1 := by
    have := htgt (e.map_source' hx); rwa [Metric.mem_sphere, dist_zero_right] at this
  have hr_ne : r ≠ 0 := hr.1.ne'
  simp only [norm_smul, Real.norm_of_nonneg hr.1.le, hxnorm, hetgnorm, mul_one,
             smul_smul, inv_mul_cancel₀ hr_ne, one_smul, e.left_inv' hx]

/-- The radial lift of `e.toFun` maps the source cone into the target cone.
For `y = r • x` with `x ∈ e.source` on the unit sphere, `‖y‖ = r` and
`‖y‖⁻¹ • y = x`, so `‖y‖ • e (‖y‖⁻¹ • y) = r • e x` lies in the target cone. -/
theorem cone_map_source (e : Equidecomp E (E ≃ᵢ E)) (S : Finset (E ≃ᵢ E))
    (_hdec : Equidecomp.IsDecompOn e.toFun e.source S) (_h0 : ∀ s ∈ S, s 0 = 0)
    (hsrc : e.source ⊆ Metric.sphere (0 : E) 1)
    (_htgt : e.target ⊆ Metric.sphere (0 : E) 1) :
    ∀ ⦃y : E⦄, y ∈ {y | ∃ r ∈ Set.Ioc (0 : ℝ) 1, ∃ x ∈ e.source, y = r • x} →
      ‖y‖ • e.toFun (‖y‖⁻¹ • y) ∈
        {y | ∃ r ∈ Set.Ioc (0 : ℝ) 1, ∃ x ∈ e.target, y = r • x} := by
  intro y hy
  obtain ⟨r, hr, x, hx, rfl⟩ := hy
  have hxnorm : ‖x‖ = 1 := by
    have h := hsrc hx
    simp only [Metric.mem_sphere, dist_zero_right] at h
    exact h
  have hrnorm : ‖r • x‖ = r := by
    rw [norm_smul, Real.norm_of_nonneg (le_of_lt hr.1), hxnorm, mul_one]
  have hinv : r⁻¹ • r • x = x := inv_smul_smul₀ (ne_of_gt hr.1) x
  rw [hrnorm, hinv]
  exact ⟨r, hr, e.toFun x, e.map_source hx, rfl⟩

/-- The radial lift of `e.invFun` maps the target cone into the source cone.
This is the symmetric counterpart of `cone_map_source`. -/
theorem cone_map_target (e : Equidecomp E (E ≃ᵢ E)) (S : Finset (E ≃ᵢ E))
    (_hdec : Equidecomp.IsDecompOn e.toFun e.source S) (_h0 : ∀ s ∈ S, s 0 = 0)
    (_hsrc : e.source ⊆ Metric.sphere (0 : E) 1)
    (htgt : e.target ⊆ Metric.sphere (0 : E) 1) :
    ∀ ⦃y : E⦄, y ∈ {y | ∃ r ∈ Set.Ioc (0 : ℝ) 1, ∃ x ∈ e.target, y = r • x} →
      ‖y‖ • e.invFun (‖y‖⁻¹ • y) ∈
        {y | ∃ r ∈ Set.Ioc (0 : ℝ) 1, ∃ x ∈ e.source, y = r • x} := by
  intro y hy
  simp only [Set.mem_setOf_eq] at hy ⊢
  obtain ⟨r, hr, x, hx, rfl⟩ := hy
  have hxs : x ∈ Metric.sphere (0 : E) 1 := htgt hx
  have hxnorm : ‖x‖ = 1 := by rwa [Metric.mem_sphere, dist_zero_right] at hxs
  have hrpos : (0 : ℝ) < r := hr.1
  have hnorm : ‖r • x‖ = r := by
    rw [norm_smul, Real.norm_of_nonneg hrpos.le, hxnorm, mul_one]
  have hef : e.invFun x ∈ e.source := e.map_target' hx
  exact ⟨r, hr, e.invFun x, hef, by rw [hnorm]; congr 1; rw [inv_smul_smul₀ hrpos.ne']⟩

/-- The radial lift map `y ↦ ‖y‖ • e (‖y‖⁻¹ • y)` has a right inverse on the target cone,
given by the analogous lift of `e.invFun`. This uses `PartialEquiv.right_inv'` and
the fact that points on the unit sphere have norm `1`. -/
theorem cone_right_inv (e : Equidecomp E (E ≃ᵢ E)) (S : Finset (E ≃ᵢ E))
    (_hdec : Equidecomp.IsDecompOn e.toFun e.source S) (_h0 : ∀ s ∈ S, s 0 = 0)
    (hsrc : e.source ⊆ Metric.sphere (0 : E) 1)
    (htgt : e.target ⊆ Metric.sphere (0 : E) 1) :
    ∀ ⦃y : E⦄, y ∈ {y | ∃ r ∈ Set.Ioc (0 : ℝ) 1, ∃ x ∈ e.target, y = r • x} →
      (fun z => ‖z‖ • e.toFun (‖z‖⁻¹ • z))
        ((fun z => ‖z‖ • e.invFun (‖z‖⁻¹ • z)) y) = y := by
  intro y hy
  obtain ⟨r, hr, x, hx, rfl⟩ := hy
  dsimp only
  have hr_pos : 0 < r := hr.1
  have hxnorm : ‖x‖ = 1 := by
    have := htgt hx; rwa [Metric.mem_sphere, dist_zero_right] at this
  have hinvnorm : ‖e.invFun x‖ = 1 := by
    have := hsrc (e.map_target' hx); rwa [Metric.mem_sphere, dist_zero_right] at this
  have hrnorm : ‖r • x‖ = r := by
    rw [norm_smul, Real.norm_of_nonneg hr_pos.le, hxnorm, mul_one]
  rw [hrnorm, inv_smul_smul₀ hr_pos.ne',
      show ‖r • e.invFun x‖ = r from by
        rw [norm_smul, Real.norm_of_nonneg hr_pos.le, hinvnorm, mul_one],
      inv_smul_smul₀ hr_pos.ne', e.right_inv' hx]

/-- **Cone lift**: an equidecomposition `e` between subsets of the unit sphere lifts to an
equidecomposition between the corresponding cones `{r • x | r ∈ (0, 1], x ∈ e.source}`
and `{r • x | r ∈ (0, 1], x ∈ e.target}`, using the same finite generating set `S`. -/
theorem cone_lift_equidecomp (e : Equidecomp E (E ≃ᵢ E)) (S : Finset (E ≃ᵢ E))
    (hdec : Equidecomp.IsDecompOn e.toFun e.source S)
    (h0 : ∀ s ∈ S, s 0 = 0)
    (hsrc : e.source ⊆ Metric.sphere (0 : E) 1)
    (htgt : e.target ⊆ Metric.sphere (0 : E) 1) :
    ∃ e' : Equidecomp E (E ≃ᵢ E),
      e'.source = {y | ∃ r ∈ Set.Ioc (0 : ℝ) 1, ∃ x ∈ e.source, y = r • x} ∧
      e'.target = {y | ∃ r ∈ Set.Ioc (0 : ℝ) 1, ∃ x ∈ e.target, y = r • x} := by
  refine ⟨Equidecomp.mk (PartialEquiv.mk
      (fun y => ‖y‖ • e.toFun (‖y‖⁻¹ • y))
      (fun y => ‖y‖ • e.invFun (‖y‖⁻¹ • y))
      {y | ∃ r ∈ Set.Ioc (0 : ℝ) 1, ∃ x ∈ e.source, y = r • x}
      {y | ∃ r ∈ Set.Ioc (0 : ℝ) 1, ∃ x ∈ e.target, y = r • x}
      ?hms ?hmt ?hli ?hri) ⟨S, ?hdec⟩, rfl, rfl⟩
  case hms => exact cone_map_source e S hdec h0 hsrc htgt
  case hmt => exact cone_map_target e S hdec h0 hsrc htgt
  case hli => exact cone_left_inv e S hdec h0 hsrc htgt
  case hri => exact cone_right_inv e S hdec h0 hsrc htgt
  case hdec => exact cone_is_decomp e S hdec h0 hsrc htgt

end Library.Geometry.BanachTarski.ConeEquidecomp
